import argparse
import json
import sys
import uuid
import structlog
from finrag.parser.pdf_layout import PDFLayoutParser

logger = structlog.get_logger(__name__)

def main() -> None:
    """Entry point for parsing command line ingestion script."""
    parser = argparse.ArgumentParser(description="FinRAG CLI Document Parser Ingest Runner.")
    parser.add_argument("--file", required=True, help="Path to local target PDF filing file.")
    parser.add_argument("--ticker", default="MOCK", help="Ticker associated with filing.")
    parser.add_argument("--period", default="Q1", help="Target quarter or period.")
    parser.add_argument("--year", type=int, default=2026, help="Target fiscal year.")
    parser.add_argument("--output", help="Optional file path to output structured JSON result.")
    
    args = parser.parse_args()

    doc_id = str(uuid.uuid4())
    layout_parser = PDFLayoutParser()

    try:
        logger.info(
            "Executing local parsing run",
            file=args.file,
            ticker=args.ticker,
            period=args.period,
            year=args.year
        )
        
        parsed_doc = layout_parser.parse(
            file_path=args.file,
            document_id=doc_id,
            ticker=args.ticker,
            period=args.period,
            year=args.year
        )

        # Print parsing summary logs
        tables_count = sum(1 for item in parsed_doc.items if item.type == "TABLE")
        text_count = sum(1 for item in parsed_doc.items if item.type == "TEXT")
        headers_count = sum(1 for item in parsed_doc.items if item.type == "HEADER")

        logger.info(
            "Parsing run completed successfully",
            total_elements=len(parsed_doc.items),
            tables_extracted=tables_count,
            text_blocks_extracted=text_count,
            headers_extracted=headers_count
        )

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(parsed_doc.model_dump(), f, indent=2)
            logger.info("Structured JSON saved to file.", output_file=args.output)
            
    except Exception as e:
        logger.error("CLI parsing run failed.", error=str(e))
        sys.exit(1)

if __name__ == "__main__":
    main()
