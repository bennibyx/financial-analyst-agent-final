# Document Chunking Strategy

## Objective

Split long 10-Q and 10-K financial documents into manageable
chunks for Nemotron-based financial information extraction.

## Chunking Strategy

1. Preserve document sections and headings.
2. Split very large sections into smaller chunks.
3. Target approximately 3,000–5,000 tokens per chunk.
4. Use approximately 200–500 tokens of overlap between chunks.
5. Keep financial tables together whenever possible.
6. Process tables separately from normal paragraphs when required.
7. Preserve page numbers and section information.
8. Assign a unique chunk ID to every chunk.

## Chunk Metadata

Each chunk should contain:

- document_id
- document_type
- company
- section
- page_number
- chunk_id
- text

## Financial Table Handling

Financial tables should be preserved as structured information
whenever possible.

Important relationships between:

- Row names
- Column names
- Values
- Units
- Reporting periods

must be maintained.

## Processing Flow

10-Q / 10-K Document
        ↓
Extract text and tables
        ↓
Identify document sections
        ↓
Create chunks
        ↓
Add metadata
        ↓
Send chunks to Nemotron
        ↓
Extract structured financial information
        ↓
Store JSON output