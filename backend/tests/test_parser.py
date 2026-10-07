from app.parser import parse_sec_filing, format_pdf_tables


def test_parse_sec_filing_sections_and_tables():
    text = """ITEM 1. BUSINESS
Our business provides AI infrastructure.

ITEM 1A. RISK FACTORS
Competition is a risk.

Revenue       Q4 FY26       Q4 FY25
68.1 billion  22.1 billion  18.5 billion
Gross Margin  72%           68%
"""

    result = parse_sec_filing(text)

    assert result["document_type"] == "SEC filing"
    assert result["section_count"] == 2

    assert result["sections"][0]["section"] == "Business"
    assert result["sections"][0]["text"] == (
        "Our business provides AI infrastructure."
    )
    assert result["sections"][0]["tables"] == []

    risk_section = result["sections"][1]

    assert risk_section["section"] == "Risk Factors"
    assert "Competition is a risk." in risk_section["text"]

    assert len(risk_section["tables"]) == 1
    assert "| Revenue | Q4 FY26 | Q4 FY25 |" in risk_section["tables"][0]
    assert "| Gross Margin | 72% | 68% |" in risk_section["tables"][0]


def test_format_pdf_tables_stacked_rows():
    text = """Revenue
1,500
1,200
1,100
Gross margin
75.0 %
74.9 %
72.4 %
"""

    result = format_pdf_tables(text)

    assert "| Revenue | 1,500 | 1,200 | 1,100 |" in result
    assert "| Gross margin | 75.0% | 74.9% | 72.4% |" in result