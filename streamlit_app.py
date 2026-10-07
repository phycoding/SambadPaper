#!/usr/bin/env python3
"""
Streamlit app: download every page of a Sambad ePaper edition and combine
them into a single downloadable PDF.

Run with:
    streamlit run streamlit_app.py
"""

import io
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import requests
import streamlit as st
from PIL import Image

BASE_URL = "https://sambadepaper.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

EPAPER_URL_PATTERN = re.compile(r"/epaper/(\d+)/(\d+)/(\d{4}-\d{2}-\d{2})/(\d+)")

SHOW_POP_PATTERN = re.compile(
    r"show_pop\(\s*'([^']+)'\s*,\s*'([^']+)'\s*,\s*'([^']+)'\s*\)"
)

HIRES_IMG_PATTERN = re.compile(
    r"(https?://[^\s\"'>]+?/epaperimages/[^\s\"'>]+?\.jpg)", re.IGNORECASE
)


def get(url: str, retries: int = 3, timeout: int = 60) -> requests.Response:
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout)
            resp.raise_for_status()
            return resp
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
    raise RuntimeError(f"Failed to GET {url}") from last_exc


def parse_epaper_url(epaper_url: str) -> dict:
    m = EPAPER_URL_PATTERN.search(epaper_url)
    if not m:
        raise ValueError("Invalid Sambad ePaper URL")
    edition, edcode, date_iso, _start_page = m.groups()
    date_obj = datetime.strptime(date_iso, "%Y-%m-%d")
    return {
        "edition": edition,
        "edcode": edcode,
        "date_dashed": date_obj.strftime("%d-%m-%Y"),
    }


def discover_detail_pages(epaper_url: str) -> dict[int, str]:
    """Fetch the listing page and build imageview_*.html detail-page URLs
    from each show_pop() handler (one per page thumbnail)."""
    info = parse_epaper_url(epaper_url)
    html = get(epaper_url).text

    matches = SHOW_POP_PATTERN.findall(html)
    if not matches:
        raise RuntimeError("No show_pop() entries found on the listing page.")

    pages = {}
    for page_no, (x, y, z) in enumerate(matches, start=1):
        pages[page_no] = (
            f"{BASE_URL}/imageview_{x}_{y}_{z}_{info['edcode']}_"
            f"{info['date_dashed']}_{page_no}_i_1_sf.html"
        )
    return pages


def resolve_hires_url(detail_url: str) -> str:
    html = get(detail_url).text
    match = HIRES_IMG_PATTERN.search(html)
    if not match:
        raise RuntimeError(f"No high-res image found on {detail_url}")
    return match.group(1)


def download_image(url: str) -> Image.Image:
    resp = get(url)
    img = Image.open(io.BytesIO(resp.content))
    img.load()
    return img.convert("RGB")


def fetch_page(page_no: int, detail_url: str) -> tuple[int, Image.Image]:
    hires_url = resolve_hires_url(detail_url)
    image = download_image(hires_url)
    return page_no, image


def build_pdf_bytes(images_by_page: dict[int, Image.Image]) -> bytes:
    ordered = [images_by_page[p] for p in sorted(images_by_page)]
    buffer = io.BytesIO()
    first, rest = ordered[0], ordered[1:]
    first.save(buffer, format="PDF", save_all=True, append_images=rest)
    return buffer.getvalue()


CUSTOM_CSS = """
<style>
#MainMenu, footer {visibility: hidden;}

.hero {
    padding: 2rem 2.25rem;
    border-radius: 18px;
    background: linear-gradient(135deg, #D7263D 0%, #8E1537 100%);
    color: #ffffff;
    margin-bottom: 1.5rem;
    box-shadow: 0 10px 30px rgba(142, 21, 55, 0.25);
}
.hero h1 {
    margin: 0 0 0.35rem 0;
    font-size: 2.1rem;
}
.hero p {
    margin: 0;
    opacity: 0.9;
    font-size: 1rem;
}

.stat-card {
    background: #F6F1EA;
    border-radius: 14px;
    padding: 1rem 1.25rem;
    text-align: center;
    border: 1px solid rgba(0,0,0,0.05);
}
.stat-card .value {
    font-size: 1.7rem;
    font-weight: 700;
    color: #D7263D;
}
.stat-card .label {
    font-size: 0.85rem;
    color: #555;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}

div[data-testid="stButton"] button {
    border-radius: 999px;
    font-weight: 600;
    padding: 0.55rem 1.4rem;
}

div[data-testid="stDownloadButton"] button {
    border-radius: 999px;
    font-weight: 600;
    background-color: #D7263D;
    color: white;
    padding: 0.6rem 1.6rem;
    border: none;
}
</style>
"""


def render_hero():
    st.markdown(
        """
        <div class="hero">
            <h1>📰 Sambad ePaper → PDF</h1>
            <p>Paste any Sambad ePaper edition link and get a single,
            high-resolution PDF of every page — built right in your browser.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_stat_cards(found: int, downloaded: int, failed: int):
    cols = st.columns(3)
    labels = [
        ("Pages Found", found),
        ("Downloaded", downloaded),
        ("Failed", failed),
    ]
    for col, (label, value) in zip(cols, labels):
        col.markdown(
            f"""
            <div class="stat-card">
                <div class="value">{value}</div>
                <div class="label">{label}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def main():
    st.set_page_config(
        page_title="Sambad ePaper → PDF",
        page_icon="📰",
        layout="centered",
        initial_sidebar_state="expanded",
    )
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    render_hero()

    with st.sidebar:
        st.header("⚙️ Settings")
        workers = st.slider("Concurrent downloads", min_value=1, max_value=12, value=6)
        show_previews = st.checkbox("Show page previews", value=True)
        preview_count = st.slider(
            "Preview thumbnails", min_value=0, max_value=12, value=6,
            disabled=not show_previews,
        )
        st.divider()
        st.caption(
            "Tip: find the edition URL by opening sambadepaper.com, picking a "
            "date/page, and copying the address bar link."
        )

    epaper_url = st.text_input(
        "ePaper edition URL",
        value="https://sambadepaper.com/epaper/1/82/2026-09-20/1",
        placeholder="https://sambadepaper.com/epaper/<edition>/<edcode>/<YYYY-MM-DD>/<page>",
    )

    build_clicked = st.button("🚀 Build PDF", type="primary")

    if build_clicked:
        try:
            with st.spinner("Discovering pages on the edition listing..."):
                detail_pages = discover_detail_pages(epaper_url)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Could not read the listing page: {exc}")
            return

        total = len(detail_pages)
        progress = st.progress(0.0, text=f"0/{total} pages processed")
        images_by_page: dict[int, Image.Image] = {}
        failures: list[tuple[int, str]] = []

        with ThreadPoolExecutor(max_workers=workers) as pool:
            future_to_page = {
                pool.submit(fetch_page, page_no, detail_url): page_no
                for page_no, detail_url in detail_pages.items()
            }
            done = 0
            for future in as_completed(future_to_page):
                page_no = future_to_page[future]
                done += 1
                try:
                    page_no, image = future.result()
                    images_by_page[page_no] = image
                except Exception as exc:  # noqa: BLE001
                    failures.append((page_no, str(exc)))
                progress.progress(done / total, text=f"{done}/{total} pages processed")

        progress.empty()
        render_stat_cards(total, len(images_by_page), len(failures))

        if failures:
            with st.expander(f"⚠️ {len(failures)} page(s) failed"):
                for page_no, reason in sorted(failures):
                    st.write(f"Page {page_no}: {reason}")

        if not images_by_page:
            st.error("No pages were downloaded — nothing to build.")
            return

        if show_previews and preview_count:
            st.subheader("Preview")
            preview_pages = sorted(images_by_page)[:preview_count]
            cols = st.columns(min(3, len(preview_pages)) or 1)
            for i, page_no in enumerate(preview_pages):
                with cols[i % len(cols)]:
                    st.image(
                        images_by_page[page_no],
                        caption=f"Page {page_no}",
                        use_container_width=True,
                    )

        with st.spinner("Assembling PDF..."):
            pdf_bytes = build_pdf_bytes(images_by_page)

        date_match = EPAPER_URL_PATTERN.search(epaper_url)
        date_part = date_match.group(3) if date_match else "edition"
        file_name = f"sambad_{date_part}.pdf"

        st.success(f"Done! {len(images_by_page)}/{total} pages assembled into a PDF.")
        st.download_button(
            "⬇️ Download PDF",
            data=pdf_bytes,
            file_name=file_name,
            mime="application/pdf",
        )


if __name__ == "__main__":
    main()
