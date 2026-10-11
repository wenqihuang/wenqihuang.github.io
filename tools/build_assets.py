"""Render the files that are generated from the page itself.

    python3 tools/build_assets.py          # all of them
    python3 tools/build_assets.py cv       # or just some: cv, md, og, icon

  cv    files/Wenqi_Huang_CV.pdf      the page's A4 print stylesheet
  md    index.md                      the page as Markdown, for AI agents
  og    images/og-card.jpg            1200 x 630 link-preview card (the hero)
  icon  images/apple-touch-icon.png   180 x 180 home-screen icon (the favicon)

Run it after changing any content (cv, md), the hero (og) or the favicon
(icon). Needs Playwright for Python
(pip install playwright); it uses the installed Google Chrome and falls back
to Playwright's own Chromium (playwright install chromium).
"""
import functools
import http.server
import pathlib
import sys
import threading

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent

# the card is the hero alone, centred, at 680 CSS px scaled to 1200 px wide
CARD_CSS = """
html { scrollbar-gutter: auto !important; }
.nav, .skip-link, .back-to-top, main, .footer, .lightbox { display: none !important; }
.hero { min-height: 100vh; display: grid; align-content: center; padding: 0 !important; margin: 0; }
"""


# the page as Markdown: the same content in reading order, minus the visual extras
# (map, buttons, decorative arrows); links are made absolute
TO_MARKDOWN = r"""() => {
  const abs = href => new URL(href, 'https://wenqihuang.me/').href;
  const inline = node => [...node.childNodes].map(n => {
    if (n.nodeType === 3) return n.textContent.replace(/[*_]/g, m => '\\' + m);  // literal * (co-first authors) and _ stay literal
    if (n.nodeType !== 1 || n.getAttribute('aria-hidden') === 'true') return '';
    const tag = n.tagName.toLowerCase(), inner = inline(n);
    if (tag === 'svg' || tag === 'button') return '';
    if (tag === 'a') return `[${inner.trim()}](${abs(n.getAttribute('href'))})`;
    if (tag === 'em' || tag === 'i') return `*${inner}*`;
    if (tag === 'strong' || tag === 'b' || n.classList.contains('me')) return `**${inner}**`;
    if (tag === 'abbr' && n.title) return n.title;
    return inner;
  }).join('');
  const text = el => el ? inline(el).replace(/\u00a0/g, ' ').replace(/\s+/g, ' ').replace(/\*\*\s*\*\*/g, '').trim() : '';
  const q = (root, sel) => root.querySelector(sel);
  const out = [];
  out.push('---', `title: ${document.title}`, `description: ${document.querySelector('meta[name="description"]').content}`,
           'url: https://wenqihuang.me/', '---', '');
  const nm = q(document, '.nm');
  out.push(`# ${text(nm.firstChild.parentNode).replace(q(nm, '.cn').textContent, '').trim()} (${q(nm, '.cn').textContent})`, '');
  out.push(text(q(document, '.say')), '', text(q(document, '.bio')), '', text(q(document, '.aside')), '');
  out.push([...document.querySelectorAll('.icons a')].map(a => `[${a.getAttribute('aria-label')}](${abs(a.getAttribute('href'))})`).join(' · '), '');
  const rows = sec => [...document.querySelectorAll(`#${sec} .rows > li`)];
  const heading = sec => `## ${text(q(document, `#${sec} .sh`))}`;

  out.push(heading('news'), '');
  rows('news').forEach(li => out.push(`- **${text(q(li, '.d'))}**: ${text(q(li, '.x'))}`));
  out.push('', heading('publications'), '', `Full list: [Google Scholar](${abs(q(document, '.shw .sub').getAttribute('href'))})`, '');
  rows('publications').forEach(li => {
    const t = q(li, '.t'), flag = q(li, '.flag');
    const links = [...li.querySelectorAll('.ln a')].map(a => `[${text(a)}](${abs(a.getAttribute('href'))})`).join(' · ');
    out.push(`- [**${text(t)}**](${abs(t.getAttribute('href'))})  `, `  ${text(q(li, '.au'))}  `,
             `  *${text(q(li, '.v'))}*${flag ? ' · ' + text(flag) : ''}${links ? ' · ' + links : ''}`);
  });
  out.push('', heading('presentations'), '');
  rows('presentations').forEach(li => {
    const flag = q(li, '.flag');
    out.push(`- **${text(q(li, '.d'))}** · ${text(q(li, '.ev'))}${flag ? ' (' + text(flag) + ')' : ''}: *${text(q(li, '.tt'))}*`);
  });
  for (const sec of ['education', 'teaching', 'service']) {
    out.push('', heading(sec), '');
    rows(sec).forEach(li => {
      const dt = q(li, '.dt');
      out.push(`- **${text(q(li, '.d'))}**: ${text(q(li, '.ev'))}${dt ? '  ' : ''}`);
      if (dt) out.push(`  ${text(dt)}`);
    });
  }
  out.push('', heading('beyond'), '', text(q(document, '#beyond .prose')), '');
  return out.join('\n');
}"""


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def serve():
    handler = functools.partial(QuietHandler, directory=str(ROOT))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}/"


def launch(p):
    try:
        return p.chromium.launch(channel="chrome")
    except Exception:
        return p.chromium.launch()


def build_cv(browser, url):
    page = browser.new_page(color_scheme="light")
    page.goto(url, wait_until="networkidle")
    page.evaluate("document.fonts.ready")
    page.wait_for_timeout(800)
    page.pdf(path=str(ROOT / "files/Wenqi_Huang_CV.pdf"), format="A4", prefer_css_page_size=True)
    page.close()


def build_md(browser, url):
    page = browser.new_page()
    page.goto(url, wait_until="networkidle")
    (ROOT / "index.md").write_text(page.evaluate(TO_MARKDOWN) + "\n", encoding="utf-8")
    page.close()


def build_og(browser, url):
    scale = 1200 / 680
    page = browser.new_page(viewport={"width": 680, "height": round(630 / scale)},
                            device_scale_factor=scale, color_scheme="light")
    page.goto(url, wait_until="networkidle")
    page.add_style_tag(content=CARD_CSS)
    page.evaluate("document.fonts.ready")
    page.wait_for_timeout(3500)  # the photo's reconstruction intro and the trajectories settle
    page.screenshot(path=str(ROOT / "images/og-card.jpg"), type="jpeg", quality=88,
                    clip={"x": 0, "y": 0, "width": 680, "height": 630 / scale})
    page.close()


def build_icon(browser, url):
    # iOS rounds the corners itself and fills transparency with black, so the
    # square goes edge to edge; the letters get more room than at favicon size
    svg = ((ROOT / "images/favicon.svg").read_text()
           .replace('rx="4"', 'rx="0"').replace('font-size="17"', 'font-size="13.5"').replace('y="23"', 'y="20.7"'))
    page = browser.new_page(viewport={"width": 180, "height": 180})
    page.set_content('<style>html,body{margin:0}svg{display:block;width:180px;height:180px}</style>' + svg)
    page.screenshot(path=str(ROOT / "images/apple-touch-icon.png"), omit_background=False)
    page.close()


def main(targets):
    builders = {"cv": build_cv, "md": build_md, "og": build_og, "icon": build_icon}
    unknown = [t for t in targets if t not in builders]
    if unknown:
        sys.exit(f"unknown target(s): {', '.join(unknown)}; choose from {', '.join(builders)}")
    server, url = serve()
    try:
        with sync_playwright() as p:
            browser = launch(p)
            for name in targets or builders:
                builders[name](browser, url)
                print(f"built {name}")
            browser.close()
    finally:
        server.shutdown()


if __name__ == "__main__":
    main(sys.argv[1:])
