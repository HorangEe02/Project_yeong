"""Insert four function-detail slides into the Lemon Aid Week 1 PPTX."""

from __future__ import annotations

import re
import shutil
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path("/Users/yeong/99_me/00_github/03_lemon_healthcare")
OUTPUT_DIR = ROOT / "records/meetings/mentoring-01/output"
PPTX_PATH = OUTPUT_DIR / "Lemon_Aid_Week1_Integrated_Briefing.pptx"
BACKUP_PATH = OUTPUT_DIR / "Lemon_Aid_Week1_Integrated_Briefing.before_function_detail.pptx"

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
APP_NS = "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
VT_NS = "http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"

ET.register_namespace("p", P_NS)
ET.register_namespace("a", A_NS)
ET.register_namespace("r", R_NS)
ET.register_namespace("", REL_NS)
ET.register_namespace("vt", VT_NS)

EMU_PER_PX = 9525
SLIDE_W = 1280
SLIDE_H = 720

BLUE = "5080F8"
NAVY = "111827"
BODY = "536174"
MUTED = "8491A5"
LINE = "DDE5F2"
BG = "FCFBF7"
PANEL = "F7FAFF"
CREAM = "FFF7E8"
MINT = "EEF8F2"


SLIDES = [
    {
        "file": 19,
        "rid": "rId25",
        "insert_after_rid": "rId7",
        "kicker": "UX 04",
        "title": "UX 기능은 기록 시작부터 저장까지 한 화면 흐름으로 이어진다",
        "subtitle": "사용자가 길게 학습하지 않아도 입력, 확인, 수정, 저장을 같은 카드 문법으로 이해하게 만든다.",
        "cards": [
            {
                "label": "01",
                "title": "시작 · 동의",
                "body": ["로그인, 이메일 확인, 건강정보 동의", "민감정보를 왜 쓰는지 먼저 안내", "처음 사용자는 3단계 안에서 핵심 이해"],
                "fill": PANEL,
            },
            {
                "label": "02",
                "title": "입력",
                "body": ["카메라, 텍스트, 라벨 촬영을 빠르게 진입", "촬영 실패나 권한 없음은 다음 행동 한 줄 표시", "식탁 앞 사용을 고려해 큰 버튼 유지"],
                "fill": CREAM,
            },
            {
                "label": "03",
                "title": "결과 확인",
                "body": ["음식 후보, 확신도, 출처, 시간 표시", "낮은 확신은 확정하지 않고 검토 상태로 노출", "AI 결과는 사용자가 확인할 수 있게 설명"],
                "fill": MINT,
            },
            {
                "label": "04",
                "title": "수정 · 저장",
                "body": ["틀린 후보, 양, 성분은 같은 카드 안에서 수정", "저장 전 preview 상태와 최종 기록을 구분", "저장 후 홈 카드와 다음 행동에 반영"],
                "fill": "F7F3FF",
            },
        ],
        "callout": "UX 상세 기능의 기준: 사용자가 멈추는 지점마다 출처, 고치기, 다음 행동을 함께 제공한다.",
    },
    {
        "file": 20,
        "rid": "rId26",
        "insert_after_rid": "rId10",
        "kicker": "음식 비전 04",
        "title": "음식 인식 기능은 후보를 만들고 사용자가 양을 확정하게 한다",
        "subtitle": "사진만으로 섭취량을 단정하지 않고, 후보와 100g 기준 프로필을 먼저 보여준 뒤 사용자 입력으로 보정한다.",
        "cards": [
            {
                "label": "01",
                "title": "입력 수집",
                "body": ["사진 또는 텍스트 식단을 받음", "라벨 OCR과 object hint는 보조 힌트로 사용", "입력 원문은 review 가능하게 유지"],
                "fill": PANEL,
            },
            {
                "label": "02",
                "title": "후보 생성",
                "body": ["YOLO 후보를 중심으로 class와 confidence 정리", "GCV/OCR은 음식명 확정이 아니라 보강 신호", "top-N 후보와 애매한 후보를 함께 전달"],
                "fill": CREAM,
            },
            {
                "label": "03",
                "title": "영양 DB 매칭",
                "body": ["공식 식품성분표와 alias 규칙으로 연결", "매칭 실패는 조용히 저장하지 않고 flag 처리", "100g 기준 영양 성격을 먼저 표시"],
                "fill": MINT,
            },
            {
                "label": "04",
                "title": "양 보정 · 저장",
                "body": ["사용자가 g 또는 인분을 입력하면 재계산", "수정값과 원 후보를 함께 snapshot으로 남김", "다음 분석에서 같은 근거를 재현 가능하게 함"],
                "fill": "F7F3FF",
            },
        ],
        "callout": "음식 비전 상세 기능의 기준: AI 판정값은 확정 기록이 아니라 사용자가 검토할 수 있는 후보다.",
    },
    {
        "file": 21,
        "rid": "rId27",
        "insert_after_rid": "rId13",
        "kicker": "알고리즘 04",
        "title": "알고리즘 기능은 계산값, 운영 규칙, 승인 상태를 분리한다",
        "subtitle": "공식 근거가 있는 계산은 고정하고, 프로젝트에서 조정할 값은 버전과 snapshot으로 추적한다.",
        "cards": [
            {
                "label": "01",
                "title": "기본 계산",
                "body": ["BMI, BMR, TDEE, HRmax 같은 기준 계산", "입력 단위와 공식 출처 버전을 함께 관리", "계산식 변경 시 영향 범위 추적"],
                "fill": PANEL,
            },
            {
                "label": "02",
                "title": "영양 상태 판정",
                "body": ["KDRIs/DRI 기준과 섭취량을 비교", "부족, 낮음, 적정, 과다 단계로 설명", "질환 가중치는 운영 규칙으로 별도 관리"],
                "fill": CREAM,
            },
            {
                "label": "03",
                "title": "Preview 승인",
                "body": ["OCR/LLM 구조화 결과는 곧바로 확정하지 않음", "Pydantic 검증 후 사용자가 수정·승인", "처방·복용량 변경 직접 안내는 차단"],
                "fill": MINT,
            },
            {
                "label": "04",
                "title": "Snapshot 저장",
                "body": ["입력값, 결과값, 알고리즘 버전을 함께 저장", "같은 입력에 같은 결과가 나왔는지 확인", "사용자에게는 참고 정보 표현만 사용"],
                "fill": "F7F3FF",
            },
        ],
        "callout": "알고리즘 상세 기능의 기준: 더 복잡한 계산보다 설명 가능성과 재현 가능성을 우선한다.",
    },
    {
        "file": 22,
        "rid": "rId28",
        "insert_after_rid": "rId16",
        "kicker": "DB/백엔드 04",
        "title": "백엔드 기능은 모든 기록을 user_id 기준 계약으로 묶는다",
        "subtitle": "앱, DB, 캐시, Agent가 같은 사용자 기준으로 동작하게 만들고 민감정보 전달 범위를 최소화한다.",
        "cards": [
            {
                "label": "01",
                "title": "인증 · 권한",
                "body": ["로그인 후 JWT로 요청 사용자 확인", "Flutter 앱은 DB에 직접 접근하지 않음", "user_id 기준 접근 제한을 기본 계약으로 둠"],
                "fill": PANEL,
            },
            {
                "label": "02",
                "title": "요청 검증",
                "body": ["FastAPI가 입력 스키마와 타입을 검증", "음식, 영양제, 프로필 요청을 같은 정책으로 처리", "실패 사유는 UX가 표시할 수 있게 분리"],
                "fill": CREAM,
            },
            {
                "label": "03",
                "title": "저장 · 캐시",
                "body": ["PostgreSQL은 장기 기록과 분석 결과 저장", "Redis는 OCR, 기준값, rate limit 같은 임시 데이터 담당", "원본과 요약 데이터의 수명을 분리"],
                "fill": MINT,
            },
            {
                "label": "04",
                "title": "Agent 전달",
                "body": ["Agent에는 DB 전체가 아니라 필요한 요약만 전달", "최근 검사값, 질환 태그, 복약 정보, 점수 중심", "agent_runs로 호출 기록과 결과를 추적"],
                "fill": "F7F3FF",
            },
        ],
        "callout": "DB/백엔드 상세 기능의 기준: 오래 보관할 데이터와 잠깐 쓸 데이터, Agent에게 보낼 데이터를 분리한다.",
    },
]


def qname(namespace: str, tag: str) -> str:
    """Build an ElementTree qualified XML name.

    Args:
        namespace: XML namespace URI.
        tag: Local tag name.

    Returns:
        A qualified tag name usable by ElementTree.
    """
    return f"{{{namespace}}}{tag}"


def emu(value: int | float) -> str:
    """Convert a 1280x720 design pixel value to PowerPoint EMU.

    Args:
        value: Pixel value in the deck design coordinate system.

    Returns:
        Integer EMU value as a string.
    """
    return str(round(value * EMU_PER_PX))


def add_text_run(parent: ET.Element, text: str, size: float, color: str, bold: bool = False) -> None:
    """Append a text run to a paragraph.

    Args:
        parent: Paragraph element.
        text: Text content.
        size: Font size in points.
        color: RGB hex color without '#'.
        bold: Whether the run should be bold.
    """
    run = ET.SubElement(parent, qname(A_NS, "r"))
    attrs = {"lang": "ko-KR", "sz": str(round(size * 100))}
    if bold:
        attrs["b"] = "1"
    rpr = ET.SubElement(run, qname(A_NS, "rPr"), attrs)
    fill = ET.SubElement(rpr, qname(A_NS, "solidFill"))
    ET.SubElement(fill, qname(A_NS, "srgbClr"), {"val": color})
    ET.SubElement(rpr, qname(A_NS, "latin"), {"typeface": "Apple SD Gothic Neo"})
    ET.SubElement(rpr, qname(A_NS, "ea"), {"typeface": "Apple SD Gothic Neo"})
    ET.SubElement(rpr, qname(A_NS, "cs"), {"typeface": "Apple SD Gothic Neo"})
    t = ET.SubElement(run, qname(A_NS, "t"))
    t.text = text


def add_text_box(
    sp_tree: ET.Element,
    shape_id: int,
    x: int,
    y: int,
    w: int,
    h: int,
    paragraphs: list[tuple[str, float, str, bool]],
    fill: str | None = None,
    line: str | None = None,
    margin: int = 0,
) -> int:
    """Add a PowerPoint text box or panel shape.

    Args:
        sp_tree: Slide shape tree.
        shape_id: Unique shape id to assign.
        x: Left coordinate in design pixels.
        y: Top coordinate in design pixels.
        w: Width in design pixels.
        h: Height in design pixels.
        paragraphs: Text paragraphs as (text, size, color, bold).
        fill: Optional RGB fill color.
        line: Optional RGB outline color.
        margin: Internal text margin in pixels.

    Returns:
        Next available shape id.
    """
    sp = ET.SubElement(sp_tree, qname(P_NS, "sp"))
    nv = ET.SubElement(sp, qname(P_NS, "nvSpPr"))
    ET.SubElement(nv, qname(P_NS, "cNvPr"), {"id": str(shape_id), "name": f"TextBox {shape_id}"})
    ET.SubElement(nv, qname(P_NS, "cNvSpPr"))
    ET.SubElement(nv, qname(P_NS, "nvPr"))
    sp_pr = ET.SubElement(sp, qname(P_NS, "spPr"))
    xfrm = ET.SubElement(sp_pr, qname(A_NS, "xfrm"))
    ET.SubElement(xfrm, qname(A_NS, "off"), {"x": emu(x), "y": emu(y)})
    ET.SubElement(xfrm, qname(A_NS, "ext"), {"cx": emu(w), "cy": emu(h)})
    prst = ET.SubElement(sp_pr, qname(A_NS, "prstGeom"), {"prst": "rect"})
    ET.SubElement(prst, qname(A_NS, "avLst"))
    if fill:
        solid = ET.SubElement(sp_pr, qname(A_NS, "solidFill"))
        ET.SubElement(solid, qname(A_NS, "srgbClr"), {"val": fill})
    else:
        ET.SubElement(sp_pr, qname(A_NS, "noFill"))
    if line:
        ln = ET.SubElement(sp_pr, qname(A_NS, "ln"), {"w": "9525"})
        solid = ET.SubElement(ln, qname(A_NS, "solidFill"))
        ET.SubElement(solid, qname(A_NS, "srgbClr"), {"val": line})
    else:
        ET.SubElement(sp_pr, qname(A_NS, "ln")).append(ET.Element(qname(A_NS, "noFill")))

    tx = ET.SubElement(sp, qname(P_NS, "txBody"))
    ET.SubElement(
        tx,
        qname(A_NS, "bodyPr"),
        {
            "wrap": "square",
            "lIns": emu(margin),
            "rIns": emu(margin),
            "tIns": emu(margin),
            "bIns": emu(margin),
        },
    )
    ET.SubElement(tx, qname(A_NS, "lstStyle"))
    for text, size, color, bold in paragraphs:
        p = ET.SubElement(tx, qname(A_NS, "p"))
        ET.SubElement(p, qname(A_NS, "pPr"), {"algn": "l"})
        add_text_run(p, text, size, color, bold)
    return shape_id + 1


def add_rect(sp_tree: ET.Element, shape_id: int, x: int, y: int, w: int, h: int, fill: str, line: str | None = None) -> int:
    """Add a simple filled rectangle.

    Args:
        sp_tree: Slide shape tree.
        shape_id: Unique shape id to assign.
        x: Left coordinate in design pixels.
        y: Top coordinate in design pixels.
        w: Width in design pixels.
        h: Height in design pixels.
        fill: RGB fill color.
        line: Optional RGB outline color.

    Returns:
        Next available shape id.
    """
    return add_text_box(sp_tree, shape_id, x, y, w, h, [], fill=fill, line=line)


def build_slide_xml(slide: dict[str, object], page_no: int, total_pages: int) -> bytes:
    """Build a new function-detail slide XML document.

    Args:
        slide: Slide content definition.
        page_no: One-based slide number in presentation order.
        total_pages: Total slide count after insertion.

    Returns:
        Serialized slide XML bytes.
    """
    root = ET.Element(qname(P_NS, "sld"), {qname(R_NS, "id"): "", "showMasterSp": "0"})
    root.attrib.pop(qname(R_NS, "id"), None)
    c_sld = ET.SubElement(root, qname(P_NS, "cSld"))
    sp_tree = ET.SubElement(c_sld, qname(P_NS, "spTree"))
    nv_grp = ET.SubElement(sp_tree, qname(P_NS, "nvGrpSpPr"))
    ET.SubElement(nv_grp, qname(P_NS, "cNvPr"), {"id": "1", "name": ""})
    ET.SubElement(nv_grp, qname(P_NS, "cNvGrpSpPr"))
    ET.SubElement(nv_grp, qname(P_NS, "nvPr"))
    grp = ET.SubElement(sp_tree, qname(P_NS, "grpSpPr"))
    xfrm = ET.SubElement(grp, qname(A_NS, "xfrm"))
    ET.SubElement(xfrm, qname(A_NS, "off"), {"x": "0", "y": "0"})
    ET.SubElement(xfrm, qname(A_NS, "ext"), {"cx": "0", "cy": "0"})
    ET.SubElement(xfrm, qname(A_NS, "chOff"), {"x": "0", "y": "0"})
    ET.SubElement(xfrm, qname(A_NS, "chExt"), {"cx": "0", "cy": "0"})

    shape_id = 2
    shape_id = add_rect(sp_tree, shape_id, 0, 0, SLIDE_W, SLIDE_H, BG)
    shape_id = add_text_box(sp_tree, shape_id, 90, 70, 280, 26, [(str(slide["kicker"]), 11.25, BLUE, True)])
    shape_id = add_text_box(sp_tree, shape_id, 90, 116, 1040, 76, [(str(slide["title"]), 30, BLUE, True)])
    shape_id = add_text_box(sp_tree, shape_id, 90, 204, 1080, 42, [(str(slide["subtitle"]), 14.25, BODY, False)])

    card_positions = [(90, 285), (655, 285), (90, 462), (655, 462)]
    for card, (x, y) in zip(slide["cards"], card_positions, strict=True):  # type: ignore[index]
        shape_id = add_text_box(sp_tree, shape_id, x, y, 535, 143, [], fill=str(card["fill"]), line=LINE, margin=18)
        shape_id = add_text_box(sp_tree, shape_id, x + 20, y + 17, 56, 24, [(str(card["label"]), 10.5, BLUE, True)])
        shape_id = add_text_box(sp_tree, shape_id, x + 82, y + 14, 410, 30, [(str(card["title"]), 15.0, NAVY, True)])
        body_paragraphs = [(f"- {line}", 10.8, BODY, False) for line in card["body"]]  # type: ignore[index]
        shape_id = add_text_box(sp_tree, shape_id, x + 24, y + 54, 485, 76, body_paragraphs)

    shape_id = add_text_box(sp_tree, shape_id, 90, 632, 1100, 38, [(str(slide["callout"]), 12.0, NAVY, True)], fill="FFF5D8", line="F0D7A4", margin=14)
    shape_id = add_text_box(sp_tree, shape_id, 65, 669, 180, 24, [("LEMON AID", 11.25, BLUE, True)])
    add_text_box(sp_tree, shape_id, 1160, 669, 80, 22, [(f"{page_no:02d} / {total_pages}", 10.5, MUTED, False)])

    clr_map = ET.SubElement(root, qname(P_NS, "clrMapOvr"))
    ET.SubElement(clr_map, qname(A_NS, "masterClrMapping"))
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def build_slide_rels() -> bytes:
    """Create the relationship XML for a new slide.

    Returns:
        Serialized relationship XML bytes.
    """
    root = ET.Element(qname(REL_NS, "Relationships"))
    ET.SubElement(
        root,
        qname(REL_NS, "Relationship"),
        {
            "Id": "rId1",
            "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout",
            "Target": "../slideLayouts/slideLayout1.xml",
        },
    )
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def update_page_number(slide_xml: bytes, page_no: int, total_pages: int) -> bytes:
    """Update the visible page-number text in an existing slide.

    Args:
        slide_xml: Original slide XML bytes.
        page_no: New one-based page number.
        total_pages: New total page count.

    Returns:
        Updated slide XML bytes.
    """
    root = ET.fromstring(slide_xml)
    ns = {"a": A_NS}
    for text in root.findall(".//a:t", ns):
        if text.text and re.fullmatch(r"\d{2} / \d{2}", text.text.strip()):
            text.text = f"{page_no:02d} / {total_pages}"
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def update_presentation_xml(xml: bytes) -> bytes:
    """Insert new slide IDs into ppt/presentation.xml.

    Args:
        xml: Original presentation XML bytes.

    Returns:
        Updated presentation XML bytes.
    """
    root = ET.fromstring(xml)
    sld_id_lst = root.find(qname(P_NS, "sldIdLst"))
    if sld_id_lst is None:
        raise ValueError("presentation.xml has no slide id list")

    existing = list(sld_id_lst)
    by_rid = {item.attrib.get(qname(R_NS, "id")): item for item in existing}
    max_id = max(int(item.attrib["id"]) for item in existing)

    for slide in SLIDES:
        rid = str(slide["rid"])
        if rid in by_rid:
            continue
        insert_after = by_rid[str(slide["insert_after_rid"])]
        idx = list(sld_id_lst).index(insert_after) + 1
        max_id += 1
        new = ET.Element(qname(P_NS, "sldId"), {"id": str(max_id), qname(R_NS, "id"): rid})
        sld_id_lst.insert(idx, new)
        by_rid[rid] = new

    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def update_presentation_rels(xml: bytes) -> bytes:
    """Add slide relationships for the inserted slides.

    Args:
        xml: Original presentation relationships XML bytes.

    Returns:
        Updated relationships XML bytes.
    """
    root = ET.fromstring(xml)
    existing_ids = {rel.attrib["Id"] for rel in root}
    for slide in SLIDES:
        rid = str(slide["rid"])
        if rid in existing_ids:
            continue
        ET.SubElement(
            root,
            qname(REL_NS, "Relationship"),
            {
                "Id": rid,
                "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide",
                "Target": f"slides/slide{slide['file']}.xml",
            },
        )
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def update_content_types(xml: bytes) -> bytes:
    """Register content types for the inserted slides.

    Args:
        xml: Original [Content_Types].xml bytes.

    Returns:
        Updated content types XML bytes.
    """
    root = ET.fromstring(xml)
    existing = {item.attrib.get("PartName") for item in root}
    for slide in SLIDES:
        part = f"/ppt/slides/slide{slide['file']}.xml"
        if part not in existing:
            ET.SubElement(
                root,
                qname(CT_NS, "Override"),
                {
                    "PartName": part,
                    "ContentType": "application/vnd.openxmlformats-officedocument.presentationml.slide+xml",
                },
            )
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def update_app_props(xml: bytes) -> bytes:
    """Update the slide count in docProps/app.xml.

    Args:
        xml: Original app properties XML bytes.

    Returns:
        Updated app properties XML bytes.
    """
    root = ET.fromstring(xml)
    for child in root:
        local = child.tag.rsplit("}", 1)[-1]
        if local == "Slides":
            child.text = "22"
        elif local == "HeadingPairs":
            for i4 in child.findall(f".//{{{VT_NS}}}i4"):
                if i4.text == "18":
                    i4.text = "22"
        elif local == "TitlesOfParts":
            vector = child.find(f"{{{VT_NS}}}vector")
            if vector is not None:
                vector.attrib["size"] = str(max(int(vector.attrib.get("size", "0")), 25))
                while len(vector) < 25:
                    item = ET.SubElement(vector, qname(VT_NS, "lpstr"))
                    item.text = "PowerPoint 프레젠테이션"
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def write_updated_pptx() -> None:
    """Create a backup and write the updated PPTX in place.

    Raises:
        FileNotFoundError: If the source PPTX is missing.
    """
    if not PPTX_PATH.exists():
        raise FileNotFoundError(PPTX_PATH)
    if not BACKUP_PATH.exists():
        shutil.copy2(PPTX_PATH, BACKUP_PATH)

    total_pages = 22
    sequence = [1, 2, 3, 4, 5, 6, 19, 7, 8, 9, 20, 10, 11, 12, 21, 13, 14, 15, 22, 16, 17, 18]
    page_by_file = {file_no: idx + 1 for idx, file_no in enumerate(sequence)}
    new_slide_by_file = {int(slide["file"]): slide for slide in SLIDES}

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pptx") as handle:
        tmp_path = Path(handle.name)

    try:
        with zipfile.ZipFile(BACKUP_PATH, "r") as zin, zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zout:
            existing_names = set(zin.namelist())
            for item in zin.infolist():
                data = zin.read(item.filename)
                match = re.fullmatch(r"ppt/slides/slide(\d+)\.xml", item.filename)
                if match:
                    slide_no = int(match.group(1))
                    data = update_page_number(data, page_by_file[slide_no], total_pages)
                elif item.filename == "ppt/presentation.xml":
                    data = update_presentation_xml(data)
                elif item.filename == "ppt/_rels/presentation.xml.rels":
                    data = update_presentation_rels(data)
                elif item.filename == "[Content_Types].xml":
                    data = update_content_types(data)
                elif item.filename == "docProps/app.xml":
                    data = update_app_props(data)
                zout.writestr(item, data)

            for file_no, slide in new_slide_by_file.items():
                slide_name = f"ppt/slides/slide{file_no}.xml"
                if slide_name not in existing_names:
                    zout.writestr(slide_name, build_slide_xml(slide, page_by_file[file_no], total_pages))
                rel_name = f"ppt/slides/_rels/slide{file_no}.xml.rels"
                if rel_name not in existing_names:
                    zout.writestr(rel_name, build_slide_rels())

        shutil.move(str(tmp_path), PPTX_PATH)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


if __name__ == "__main__":
    write_updated_pptx()
