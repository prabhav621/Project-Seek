import asyncio
import os
import tempfile
from unittest.mock import patch, MagicMock

@patch('src.ingestion.document.genai.Client')
async def test_document_extraction(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    
    mock_file = MagicMock()
    mock_file.name = "test_file.txt"
    mock_client.files.upload.return_value = mock_file
    
    with patch('src.ingestion.document.generate_content_with_retry') as mock_generate:
        mock_response = MagicMock()
        mock_response.text = "Attention is all you need"
        mock_generate.return_value = mock_response
        
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test_doc.md")
            with open(test_file, "w") as f:
                f.write("Dummy content")
                
            # Now we mock the settings so it doesn't fail on init inside other modules
            with patch('src.config.settings.gemini_api_key', 'mock_key'):
                from src.ingestion.document import extract_document_text
                extracted_text = await extract_document_text(test_file, "text/markdown")
            
                assert extracted_text == "Attention is all you need"
                print("Mock extraction successful.")

if __name__ == "__main__":
    asyncio.run(test_document_extraction())
