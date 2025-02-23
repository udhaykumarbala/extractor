import pdfplumber
import io

def test_pdf_reading():
    try:
        # Open and read the PDF file
        with pdfplumber.open('018.02.17.25.768217.pdf') as pdf:
            # Get the number of pages
            print(f"Number of pages: {len(pdf.pages)}")
            
            # Try to extract text from each page
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
        print(f"Error reading PDF: {str(e)}")

if __name__ == "__main__":
    test_pdf_reading() 