import re
import os
from pathlib import Path
from ebooklib import epub


class EpubConverter:
    def __init__(self, folder_path: str, book_title: str, author: str, language: str, epub_dir: str = "."):
        """
        Initialize EPUB converter with folder containing txt files.
        
        Args:
            folder_path: Path to folder containing .txt files to convert
            author: Book author name
            language: Book language code
            epub_dir: Directory where EPUB files will be saved
            book_title: Custom book title
        """
        self.folder_path = Path(folder_path)
        self.author = author
        self.language = language
        self.output_dir = Path(epub_dir)  # FIX: Use the correct input parameter 'epub_dir'
        self.custom_title = book_title
        self.title = None
        self.book = epub.EpubBook()
        
        # Create output directory if it doesn't exist
        self.output_dir.mkdir(exist_ok=True)
        
        # Verify folder exists
        if not self.folder_path.exists():
            raise ValueError(f"Folder not found: {folder_path}")
        if not self.folder_path.is_dir():
            raise ValueError(f"Path is not a directory: {self.folder_path}")
    
    def _load_txt_files(self) -> list[tuple[str, str]]:
        """
        Load all .txt files from folder in alphanumeric order.
        
        Returns:
            List of tuples (filename, content)
        """
        txt_files = sorted(self.folder_path.glob("*.txt"))
        
        if not txt_files:
            raise ValueError(f"No .txt files found in {self.folder_path}")
        
        files_content = []
        for txt_file in txt_files:
            try:
                content = txt_file.read_text(encoding='utf-8')
                files_content.append((txt_file.stem, content))
            except Exception as e:
                print(f"⚠️  Error reading {txt_file.name}: {e}")
                continue
        
        return files_content
        
    def _sanitize_filename(self, text: str) -> str:
        """Convert text to safe filename by removing invalid characters."""
        safe = re.sub(r'[<>:"/\\|?*]', '', text)
        safe = safe[:100].strip()
        return safe if safe else "book"
    
    def _extract_title(self, files_content: list[tuple[str, str]]) -> str:
        """Extract book title from first line of first file or use custom title."""
        if self.custom_title:
            return self.custom_title
        
        if not files_content:
            return "Untitled"
        
        first_content = files_content[0][1]
        first_line = first_content.split('\n')[0].strip()
        return first_line if first_line else "Untitled"
    
    def get_title(self) -> str:
        """Get the title of the book."""
        return self.title if self.title else "Untitled"
    
    def create_epub(self) -> str:
        """
        Create EPUB file from all .txt files in folder.
        
        Returns:
            Full path of created EPUB file
        """
        files_content = self._load_txt_files()
        
        if not files_content:
            raise ValueError("No content to create EPUB")
        
        title = self._extract_title(files_content)
        self.title = title
        self.book.set_title(title)
        self.book.set_language(self.language)
        self.book.add_author(self.author)
        
        chapters = []
        
        for i, (filename, content) in enumerate(files_content, 1):
            chapter = epub.EpubHtml(
                title=filename,
                file_name=f'chap_{i:03d}.xhtml',
                lang=self.language
            )
            
            paragraphs = content.split('\n')
            html_content = f'<h1>{paragraphs[0]}</h1>'
            
            for para in paragraphs[1:]:
                if para.strip():
                    html_content += f'<p>{para}</p>'
            
            chapter.set_content(html_content)
            self.book.add_item(chapter)
            chapters.append(chapter)
        
        self.book.toc = tuple(chapters)
        self.book.add_item(epub.EpubNcx())
        self.book.add_item(epub.EpubNav())
        self.book.spine = ['nav'] + chapters
        
        # FIX: Use the correct variables and function call to write the file
        safe_title = self._sanitize_filename(self.title)
        epub_path = self.output_dir / f"{safe_title}.epub"
        
        epub.write_epub(epub_path, self.book, {})
        
        print(f"✅ EPUB for '{self.title}' created at: {epub_path}")
        
        return str(epub_path)