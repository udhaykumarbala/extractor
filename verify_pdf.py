import pdfplumber
import sys

def verify_pdf(filename: str) -> None:
    """Verify if a PDF file can be read and extract its contents."""
    print(f"Attempting to read PDF file: {filename}")
    
    try:
        with pdfplumber.open(filename) as pdf:
            print(f"\nPDF opened successfully!")
            print(f"Number of pages: {len(pdf.pages)}")
            
            for i, page in enumerate(pdf.pages):
                print(f"\nPage {i+1}:")
                try:
                    text = page.extract_text()
                    if text:
                        print(f"Text length: {len(text)}")
                        print("First 200 characters:")
                        print("-" * 50)
                        print(text[:200])
                        print("-" * 50)
                    else:
                        print("No text extracted from this page")
                except Exception as e:
                    print(f"Error extracting text from page {i+1}: {str(e)}")
    
    except Exception as e:
        print(f"Error opening PDF: {str(e)}")
        print("\nFile details:")
        with open(filename, 'rb') as f:
            header = f.read(10)
            print(f"First 10 bytes: {header}")

if __name__ == "__main__":
    filename = "018.02.17.25.768217.pdf"
    verify_pdf(filename) 