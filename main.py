from scraper import WebScraper
from epub_converter import EpubConverter
from email_sender import EmailSender

if __name__ == "__main__":
    book_url = input("Enter the main book URL (the one with the chapter list): ").strip()
    
    if not book_url:
        print("Book URL not provided.")
        exit(1)

    try:
        start_chapter = int(input("Enter the starting chapter number: "))
        end_chapter = int(input("Enter the ending chapter number: "))
    except ValueError:
        print("Invalid chapter number. Please enter integers.")
        exit(1)

    book_title = input("Enter book name: ")
    author = input("Enter author name: ")
    language = input("Enter book language: ")

    send_email = input("\nDo you want to send the EPUB via email? (y/n): ").strip().lower()

    scraper = WebScraper(book_url, start_chapter, end_chapter)
    print("Starting scraping...")
    path = scraper.scrape()

    if path and any(path.iterdir()):
        converter = EpubConverter(folder_path=path, author=author, language=language, book_title=book_title)
        filename = converter.create_epub()

        if send_email == 'y':
            email_sender = EmailSender()
            
            sender_email, sender_password, recipient_email = email_sender.get_credentials()
            
            success = email_sender.send_epub(
                epub_file=filename,
                sender_email=sender_email,
                sender_password=sender_password,
                recipient_email=recipient_email,
                subject=f"EPUB: {converter.get_title()}",
                body="Here is your scraped EPUB book."
            )
            
            if not success:
                print("\n⚠️  Email sending failed, but EPUB file is saved locally.")
    else:
        print("Scraping failed or no chapters were found in the specified range.")