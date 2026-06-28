import smtplib
import os
import json
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

class EmailSender:
    def __init__(self, smtp_server: str = "smtp.gmail.com", smtp_port: int = 587, config_file: str = "email_config.json"):
        """
        Initialize email sender.
        
        Args:
            smtp_server: SMTP server address (default: Gmail)
            smtp_port: SMTP server port (default: 587 for TLS)
            config_file: Path to configuration file for storing credentials.
        """
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.config_file = Path(config_file)
    
    def load_credentials(self) -> dict | None:
        """
        Load email credentials from the JSON config file.
        
        Returns:
            A dictionary with credentials or None if the file doesn't exist or is invalid.
        """
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    if all(k in config for k in ['sender_email', 'sender_password', 'recipient_email']):
                        return config
            except (json.JSONDecodeError, IOError):
                return None
        return None
    
    def save_credentials(self, sender_email: str, sender_password: str, recipient_email: str):
        """
        Save email credentials to the JSON config file.
        
        Args:
            sender_email: Sender's email address.
            sender_password: Sender's email password.
            recipient_email: Default recipient's email address.
        """
        config = {
            "sender_email": sender_email,
            "sender_password": sender_password,
            "recipient_email": recipient_email
        }
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=4)
        except IOError as e:
            print(f"Error saving credentials: {e}")

    def send_epub(self, 
                  epub_file: str,
                  sender_email: str,
                  sender_password: str,
                  recipient_email: str,
                  subject: str = "EPUB Book",
                  body: str = "Please find the attached EPUB file.") -> tuple[bool, str]:
        """
        Send EPUB file via email.
        
        Returns:
            A tuple (bool, str) indicating success and a status message.
        """
        if not os.path.exists(epub_file):
            return False, f"Error: File '{epub_file}' not found."
        
        try:
            msg = MIMEMultipart()
            msg['From'] = sender_email
            msg['To'] = recipient_email
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))
            
            with open(epub_file, 'rb') as attachment:
                part = MIMEBase('application', 'epub+zip')
                part.set_payload(attachment.read())
            
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename= {os.path.basename(epub_file)}')
            msg.attach(part)
            
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(sender_email, sender_password)
            text = msg.as_string()
            server.sendmail(sender_email, recipient_email, text)
            server.quit()
            
            return True, f"Email sent successfully to {recipient_email}"
            
        except smtplib.SMTPAuthenticationError:
            return False, "Authentication failed. Check email/password.\nFor Gmail, you may need an App Password."
        except Exception as e:
            return False, f"An error occurred: {e}"