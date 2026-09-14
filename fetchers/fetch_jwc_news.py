"""
抓取西南交通大学的「研究生」相关通知（研究生院 + 信息科学与技术学院）

两个源的页面结构完全不同，所以各写一个解析函数：

1. 研究生院官网 · 通知公告（新版「全部」栏目）
   https://gsnews.swjtu.edu.cn/tzggnew/qb.htm （静态 HTML，不需要登录）
   每条通知形如：
     <li><a href="../info/1637/34844.htm">标题</a><time class="fs14">2026.09.12</time></li>
   注意：老的 https://gsnews.swjtu.edu.cn/tzgg.htm 标着「通知公告(旧版)」，
   内容停在 2024 年，不要再改回去用它。

2. 信息科学与技术学院官网 · 教育教学 > 研究生教育 > 通知公告
   学院官网是 Vue 单页应用，HTML 里只有 <div id="app"></div>，抓不到正文，
   只能调它自己的公开接口：
     POST https://sist.swjtu.edu.cn/dev-api/web/node
     {"id": "<栏目encodeId>", "pageNum": 1, "pageSize": 20, "sitetype": "..."}
   返回 {"code":200,"total":991,"rows":[{"id","title","publishTime",...}]}
   详情页是前端路由，链接要自己拼：
     https://sist.swjtu.edu.cn/pc/{secondId}/{navId}?id={文章id}&lang=cn

【2026-09 改版说明】原脚本抓的是本科生院（bksy.swjtu.edu.cn），研究生用不上。
现在换成上面两个源，本科生通知不再抓取。输出文件名（jwc_news.json）和字段
（title/date/url）保持不变，下游的 summarize.py / send_email.py 不用改。
"""
import json
import random
import re
import socket
import time
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from urllib3.util import connection as urllib3_connection

# —— 数据源 1：研究生院通知公告（新版） ——
GS_LIST_URL = "https://gsnews.swjtu.edu.cn/tzggnew/qb.htm"
SOURCE_GS = "研究生院"

# —— 数据源 2：信息学院「教育教学 > 研究生教育 > 通知公告」 ——
SIST_SITE = "https://sist.swjtu.edu.cn"
SIST_API_URL = SIST_SITE + "/dev-api/web/node"
SIST_SITE_TYPE = "NEd5n92EMIpyyBslaNqsRgE"    # 接口要求的站点标识，取自官网前端
SIST_NAV_ID = "1yaM_T4qiBsFULvLXHbMflQ"       # 研究生教育 > 通知公告 的栏目 id
SIST_SECOND_ID = "NrWCF8Dr-wmmIxdXvZPeCQY"     # 上级栏目「教育教学」的 id，拼详情链接用
SIST_PAGE_SIZE = 20
SOURCE_SIST = "信息学院"

REQUEST_TIMEOUT = 15
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

# 新版通知公告的文章链接特征：/info/栏目ID/文章ID.htm
_ARTICLE_PATH_RE = re.compile(r"/info/\d+/\d+\.htm")
# 兼容 2026.09.12 / 2026-09-10 17:00:23 / 2026/9/5 / 2026年9月13日 几种写法
_DATE_RE = re.compile(r"(\d{4})\s*[年./-]\s*(\d{1,2})\s*[月./-]\s*(\d{1,2})")


def normalize_date(text):
    """把各种日期写法统一成 2026-09-12，识别不出来就返回空字符串"""
    if not text:
        return ""
    match = _DATE_RE.search(text)
    if not match:
        return ""
    year, month, day = match.groups()
    return "%s-%02d-%02d" % (year, int(month), int(day))


def sist_article_url(article_id):
    """学院官网是前端路由，详情链接要按它的规则拼出来"""
    return "%s/pc/%s/%s?id=%s&lang=cn" % (
        SIST_SITE,
        SIST_SECOND_ID,
        SIST_NAV_ID,
        article_id,
    )


def prefer_ipv4():
    """让 requests 只走 IPv4。

    GitHub Actions 的 runner 上抓到过 `[Errno 101] Network is unreachable`
    （IPv6 没有出网路由时会出现这个报错），学校站点都是 IPv4 能通的，
    所以这里强制 IPv4 作为兜底，不影响本地运行。
    """
    urllib3_connection.allowed_gai_family = lambda: socket.AF_INET


def parse_gs_html(html, page_url=GS_LIST_URL):
    """解析研究生院通知公告页（静态 HTML）"""
    soup = BeautifulSoup(html, "html.parser")
    items = []

    for link in soup.find_all("a", href=lambda href: href and _ARTICLE_PATH_RE.search(href)):
        title = link.get_text(strip=True)
        if not title:
            continue

        # 日期在同一个 <li> 里的 <time> 标签中，形如 2026.09.12
        date_str = ""
        li = link.find_parent("li")
        if li is not None:
            time_tag = li.find("time")
            if time_tag is not None:
                date_str = normalize_date(time_tag.get_text(strip=True))

        items.append({
            "title": title,
            "date": date_str,
            "url": urljoin(page_url, link["href"]),
            "source": SOURCE_GS,
        })

    return items


def parse_sist_response(payload):
    """解析学院官网接口返回的 JSON"""
    rows = (payload or {}).get("rows") or []
    items = []

    for row in rows:
        title = (row.get("title") or "").strip()
        article_id = row.get("id") or ""
        if not title or not article_id:
            continue
        items.append({
            "title": title,
            "date": normalize_date(row.get("publishTime") or ""),
            "url": sist_article_url(article_id),
            "source": SOURCE_SIST,
        })

    return items


def merge_items(sources):
    """多来源合并：按标题去重（先出现的来源优先），按日期倒序，没日期的沉底"""
    seen = set()
    merged = []

    for items in sources:
        for item in items:
            title = item.get("title")
            if not title or title in seen:
                continue
            seen.add(title)
            merged.append(item)

    merged.sort(key=lambda item: item.get("date") or "", reverse=True)
    return merged


def fetch_gs_news():
    """抓研究生院通知公告（新版）"""
    time.sleep(random.uniform(1, 3))

    resp = requests.get(GS_LIST_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    if not resp.encoding or resp.encoding.lower() == "iso-8859-1":
        resp.encoding = resp.apparent_encoding or "utf-8"  # 避免中文乱码
    resp.raise_for_status()

    return parse_gs_html(resp.text, GS_LIST_URL)


def fetch_sist_news():
    """抓信息学院「研究生教育 > 通知公告」（走官网自己的公开接口）"""
    time.sleep(random.uniform(1, 3))
    prefer_ipv4()

    payload = {
        "id": SIST_NAV_ID,
        "pageNum": 1,
        "pageSize": SIST_PAGE_SIZE,
        "sitetype": SIST_SITE_TYPE,
    }
    try:
        resp = requests.post(SIST_API_URL, json=payload, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as exc:
        # 这个源只在 CI 上偶尔连不通，报错里带上解析结果，方便下次一眼定位
        raise RuntimeError("学院站点连接失败（%s）：%s" % (_describe_host("sist.swjtu.edu.cn"), exc)) from exc
    resp.raise_for_status()

    data = resp.json()
    if data.get("code") != 200:
        raise RuntimeError("学院接口返回异常：%s" % (data.get("msg") or data.get("code")))

    return parse_sist_response(data)


def _describe_host(host, port=443):
    """把主机解析到的 IP 拼成一行，用于报错时说明走的是哪个地址"""
    try:
        addrs = socket.getaddrinfo(host, port)
    except Exception as exc:  # 解析都失败也要能报错
        return "解析失败：%s" % exc
    ips = sorted({addr[4][0] for addr in addrs})
    return "解析到 " + "/".join(ips) if ips else "没有解析到地址"


def fetch_jwc_news():
    """两个源各自独立抓取：一个挂了另一个照常出简报，都挂了才算失败"""
    sources = []
    errors = []

    for name, func in (("研究生院", fetch_gs_news), ("信息学院研究生教育", fetch_sist_news)):
        try:
            items = func()
        except Exception as exc:  # 单个源失败不该让整份简报发不出去
            errors.append("%s：%s" % (name, exc))
            print("[警告] %s抓取失败，跳过：%s" % (name, exc))
            continue
        print("· %s：%d 条" % (name, len(items)))
        sources.append(items)

    if not sources:
        raise RuntimeError("所有来源都抓取失败：" + "；".join(errors))

    return merge_items(sources)


if __name__ == "__main__":
    news = fetch_jwc_news()

    print("\n抓取到 %d 条研究生通知\n" % len(news))
    for i, item in enumerate(news[:20], 1):
        print("%d. [%s] %s" % (i, item["date"], item["title"]))
        print("   %s\n" % item["url"])

    output = {
        "fetched_at": datetime.now().isoformat(),
        "source": "swjtu_yjs",
        "items": news,
    }
    with open("jwc_news.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("已保存到 jwc_news.json（共 %d 条）" % len(news))
