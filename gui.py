import sys
import json
import uuid
import re
from pathlib import Path
import shutil
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QProgressBar, QTableWidget, QTableWidgetItem,
    QMessageBox, QInputDialog, QFrame, QDialog, QDialogButtonBox, QFormLayout,
    QHeaderView, QAbstractItemView
)
from PySide6.QtCore import Qt, QThread, Signal, QObject
from ebooklib import epub

from src.scraper import WebScraper
from src.epub_converter import EpubConverter
from src.email_sender import EmailSender

class ScrapeWorker(QObject):
    """Worker thread for running the scraping process."""
    finished = Signal(str)
    error = Signal(str)
    progress = Signal(int)

    def __init__(self, url, start_chap, end_chap, title, auth, lang):
        super().__init__()
        self.url = url
        self.start_chap = start_chap
        self.end_chap = end_chap
        self.title = title
        self.auth = auth
        self.lang = lang

    def run(self):
        try:
            self.progress.emit(10)
            scraper = WebScraper(self.url, self.start_chap, self.end_chap)
            temp_path = scraper.scrape()
            self.progress.emit(50)

            if not temp_path or not any(temp_path.iterdir()):
                raise Exception("Scraping failed or no chapters were found.")

            Path("epubs").mkdir(exist_ok=True)
            converter = EpubConverter(
                folder_path=temp_path,
                author=self.auth,
                language=self.lang,
                book_title=self.title,
                epub_dir="epubs"
            )
            epub_path = converter.create_epub()
            self.progress.emit(100)
            self.finished.emit(epub_path)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            if temp_path and temp_path.exists():
                shutil.rmtree(temp_path)


class EditDialog(QDialog):
    """A dialog for editing EPUB metadata."""
    def __init__(self, metadata, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Metadata")
        self.layout = QFormLayout(self)

        self.title_edit = QLineEdit(metadata.get('title', ''))
        self.author_edit = QLineEdit(metadata.get('author', ''))
        self.lang_edit = QLineEdit(metadata.get('language', ''))

        self.layout.addRow("Title:", self.title_edit)
        self.layout.addRow("Author:", self.author_edit)
        self.layout.addRow("Language:", self.lang_edit)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.layout.addWidget(self.buttons)

    def get_metadata(self):
        return {
            "title": self.title_edit.text(),
            "author": self.author_edit.text(),
            "language": self.lang_edit.text(),
        }

class CredentialsDialog(QDialog):
    """A dialog for entering email credentials."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Email Credentials")
        self.layout = QFormLayout(self)

        self.sender_edit = QLineEdit()
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.recipient_edit = QLineEdit()

        self.layout.addRow("Your Email:", self.sender_edit)
        self.layout.addRow("Your Password:", self.password_edit)
        self.layout.addRow("Recipient Email:", self.recipient_edit)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.layout.addWidget(self.buttons)

    def get_credentials(self):
        return {
            "sender_email": self.sender_edit.text(),
            "sender_password": self.password_edit.text(),
            "recipient_email": self.recipient_edit.text(),
        }

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EPUB Scraper")
        self.setGeometry(100, 100, 1200, 800)
        self.email_sender = EmailSender()

        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)
        self.setCentralWidget(main_widget)

        self._create_left_panel()
        self._create_right_panel()

        main_layout.addWidget(self.left_panel)
        main_layout.addWidget(self.right_panel)

        self.update_library()

    def _create_left_panel(self):
        self.left_panel = QFrame()
        self.left_panel.setFixedWidth(450)
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title_label = QLabel("Scraping Hub")
        title_label.setStyleSheet("font-size: 20px; font-weight: bold;")
        left_layout.addWidget(title_label)

        self.url_input = QLineEdit(placeholderText="Book URL")
        self.title_input = QLineEdit(placeholderText="Book Title")
        self.author_input = QLineEdit(placeholderText="Author")
        self.lang_input = QLineEdit(placeholderText="Language (e.g., en)", text="en")
        
        chapter_layout = QHBoxLayout()
        self.start_chapter_input = QLineEdit(placeholderText="Start Chapter")
        self.end_chapter_input = QLineEdit(placeholderText="End Chapter")
        chapter_layout.addWidget(self.start_chapter_input)
        chapter_layout.addWidget(self.end_chapter_input)

        left_layout.addWidget(self.url_input)
        left_layout.addLayout(chapter_layout)
        left_layout.addWidget(self.title_input)
        left_layout.addWidget(self.author_input)
        left_layout.addWidget(self.lang_input)

        self.start_button = QPushButton("Start Scraping")
        self.start_button.clicked.connect(self.start_scraping)
        left_layout.addWidget(self.start_button)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        left_layout.addWidget(self.progress_bar)

    def _create_right_panel(self):
        self.right_panel = QFrame()
        right_layout = QVBoxLayout(self.right_panel)

        lib_label = QLabel("My Library")
        lib_label.setStyleSheet("font-size: 20px; font-weight: bold;")
        right_layout.addWidget(lib_label)

        self.epub_table = QTableWidget()
        self.epub_table.setColumnCount(3)
        self.epub_table.setHorizontalHeaderLabels(["Title", "Author", "Language"])
        self.epub_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.epub_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.epub_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.epub_table.setAlternatingRowColors(True)
        right_layout.addWidget(self.epub_table)

        lib_button_layout = QHBoxLayout()
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.update_library)
        self.edit_button = QPushButton("Edit Metadata")
        self.edit_button.clicked.connect(self.edit_metadata)
        self.send_button = QPushButton("Send via Email")
        self.send_button.clicked.connect(self.send_selected_epub)
        self.delete_button = QPushButton("Delete")
        self.delete_button.clicked.connect(self.delete_epub)
        
        lib_button_layout.addWidget(self.refresh_button)
        lib_button_layout.addWidget(self.edit_button)
        lib_button_layout.addWidget(self.send_button)
        lib_button_layout.addWidget(self.delete_button)
        right_layout.addLayout(lib_button_layout)

    def start_scraping(self):
        try:
            start_chap = int(self.start_chapter_input.text())
            end_chap = int(self.end_chapter_input.text())
        except ValueError:
            QMessageBox.critical(self, "Error", "Chapter numbers must be integers.")
            return

        url = self.url_input.text()
        title = self.title_input.text()
        author = self.author_input.text()
        lang = self.lang_input.text()

        if not all([url, title, author, lang]):
            QMessageBox.critical(self, "Error", "All fields must be filled.")
            return

        self.start_button.setEnabled(False)
        self.progress_bar.setValue(5)

        self.thread = QThread()
        self.worker = ScrapeWorker(url, start_chap, end_chap, title, author, lang)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.on_scraping_finished)
        self.worker.error.connect(self.on_scraping_error)
        self.worker.progress.connect(self.progress_bar.setValue)
        self.thread.start()

    def on_scraping_finished(self, epub_path):
        QMessageBox.information(self, "Success", f"EPUB created successfully at:\n{epub_path}")
        self.cleanup_thread()
        self.update_library()

    def on_scraping_error(self, error_msg):
        QMessageBox.critical(self, "Scraping Error", error_msg)
        self.cleanup_thread()

    def cleanup_thread(self):
        self.progress_bar.setValue(0)
        self.start_button.setEnabled(True)
        if hasattr(self, 'thread') and self.thread.isRunning():
            self.thread.quit()
            self.thread.wait()

    def update_library(self):
        self.epub_table.setRowCount(0)
        epub_dir = Path("epubs")
        if not epub_dir.exists(): return

        files = sorted(epub_dir.glob("*.epub"), key=lambda f: f.stat().st_mtime, reverse=True)
        self.epub_table.setRowCount(len(files))

        for row, epub_file in enumerate(files):
            try:
                book = epub.read_epub(epub_file)
                title = book.get_metadata('DC', 'title')[0][0]
                author = book.get_metadata('DC', 'creator')[0][0]
                lang = book.get_metadata('DC', 'language')[0][0]
            except Exception:
                title, author, lang = epub_file.stem, "Unknown", "Unknown"
            
            self.epub_table.setItem(row, 0, QTableWidgetItem(title))
            self.epub_table.setItem(row, 1, QTableWidgetItem(author))
            self.epub_table.setItem(row, 2, QTableWidgetItem(lang))
            self.epub_table.item(row, 0).setData(Qt.UserRole, str(epub_file))

    def get_selected_epub_path(self):
        selected_rows = self.epub_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "Warning", "No EPUB selected from the library.")
            return None
        
        item = self.epub_table.item(selected_rows[0].row(), 0)
        return Path(item.data(Qt.UserRole))

    def delete_epub(self):
        epub_path = self.get_selected_epub_path()
        if not epub_path: return

        if QMessageBox.question(self, "Delete EPUB", f"Delete {epub_path.name}?") == QMessageBox.Yes:
            try:
                epub_path.unlink()
                self.update_library()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error deleting file: {e}")

    def edit_metadata(self):
        epub_path = self.get_selected_epub_path()
        if not epub_path: return

        try:
            old_book = epub.read_epub(epub_path)
            metadata = {
                'title': old_book.get_metadata('DC', 'title')[0][0],
                'author': old_book.get_metadata('DC', 'creator')[0][0],
                'language': old_book.get_metadata('DC', 'language')[0][0]
            }
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not read metadata from the EPUB file. It might be corrupted.\n\nDetails: {e}")
            return

        dialog = EditDialog(metadata, self)
        if dialog.exec():
            new_meta = dialog.get_metadata()

            if not all([new_meta['title'], new_meta['author'], new_meta['language']]):
                QMessageBox.warning(self, "Validation Error", "Title, Author, and Language cannot be empty.")
                return

            try:
                # Rebuild the book from scratch to guarantee no corruption is carried over.
                new_book = epub.EpubBook()

                new_book.set_title(new_meta['title'])
                new_book.set_language(new_meta['language'])
                new_book.add_author(new_meta['author'])
                new_book.set_identifier(uuid.uuid4().urn)
                new_book.items = old_book.items

                chapters = [item for item in new_book.items if isinstance(item, epub.EpubHtml)]
                new_book.toc = tuple(chapters)
                
                new_book.add_item(epub.EpubNcx())
                new_book.add_item(epub.EpubNav())
                new_book.spine = ['nav'] + chapters

                # --- Handle file renaming ---
                new_filename = self._sanitize_filename(new_meta['title']) + ".epub"
                new_path = epub_path.parent / new_filename

                epub.write_epub(new_path, new_book, {})

                # If the filename has changed, delete the old file
                if new_path != epub_path:
                    epub_path.unlink()
                
                self.update_library()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not save metadata: {e}")

    def _sanitize_filename(self, text: str) -> str:
        """Convert text to a safe filename by removing invalid characters."""
        safe = re.sub(r'[<>:"/\\|?*]', '', text)
        safe = safe[:100].strip()
        return safe if safe else "book"

    def send_selected_epub(self):
        epub_path = self.get_selected_epub_path()
        if not epub_path: return

        creds = self.email_sender.load_credentials()
        if not creds:
            dialog = CredentialsDialog(self)
            if dialog.exec():
                creds = dialog.get_credentials()
                if not all(creds.values()):
                    QMessageBox.warning(self, "Warning", "All credential fields are required.")
                    return
                self.email_sender.save_credentials(**creds)
            else:
                return # User cancelled

        success, message = self.email_sender.send_epub(
            epub_file=str(epub_path),
            subject=f"EPUB: {epub_path.stem}",
            **creds
        )

        if success:
            QMessageBox.information(self, "Success", message)
        else:
            QMessageBox.critical(self, "Email Error", message)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())