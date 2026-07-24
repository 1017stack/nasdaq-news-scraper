"""
Notification System
Sends email and SMS alerts for high-impact news events
Uses SendGrid for email, Twilio for SMS
"""

import asyncio
from datetime import datetime
from typing import List, Dict, Optional
import os

# Try to import SendGrid
try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail, Email, To, Content
    SENDGRID_AVAILABLE = True
except ImportError:
    SENDGRID_AVAILABLE = False

# Try to import Twilio
try:
    from twilio.rest import Client as TwilioClient
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False


class NotificationManager:
    """
    Manages notifications for high-impact news events.
    Supports email (SendGrid) and SMS (Twilio).
    """

    def __init__(self):
        self.sendgrid_client = None
        self.twilio_client = None
        self.from_email = os.getenv("NOTIFICATION_EMAIL", "alerts@nasdaq-news.com")
        self.from_phone = os.getenv("TWILIO_PHONE_NUMBER")

        # Initialize SendGrid if key available
        sendgrid_key = os.getenv("SENDGRID_API_KEY")
        if SENDGRID_AVAILABLE and sendgrid_key:
            self.sendgrid_client = SendGridAPIClient(sendgrid_key)

        # Initialize Twilio if credentials available
        twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
        twilio_token = os.getenv("TWILIO_AUTH_TOKEN")
        if TWILIO_AVAILABLE and twilio_sid and twilio_token:
            self.twilio_client = TwilioClient(twilio_sid, twilio_token)

    async def should_notify(self, news_item: Dict) -> bool:
        """
        Determine if a news item warrants notification.
        Only high impact + significant sentiment moves.
        """
        # Must be high impact
        if news_item.get("impact_level") != "high":
            return False

        # Significant sentiment (positive or negative)
        sentiment = news_item.get("sentiment_score", 0)
        if abs(sentiment) < 30:
            return False

        # High impact categories that matter
        significant_categories = {
            "earnings", "ma", "sec", "management", "workforce"
        }

        category = news_item.get("category", "general")
        if category not in significant_categories:
            # Still notify if sentiment is extreme
            if abs(sentiment) < 60:
                return False

        return True

    def format_email_subject(self, news_items: List[Dict]) -> str:
        """Format email subject line"""
        if len(news_items) == 1:
            item = news_items[0]
            ticker = item.get("ticker", "UNKNOWN")
            category = item.get("category", "NEWS").upper()
            sentiment = item.get("sentiment_score", 0)
            direction = "🚀" if sentiment > 0 else "📉"
            return f"[ALERT] {ticker}: {category} {direction}"
        else:
            return f"[ALERT] {len(news_items)} High-Impact News Items"

    def format_email_body(self, news_items: List[Dict]) -> str:
        """Format HTML email body"""
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f5f7; margin: 0; padding: 20px; }
                .container { max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
                .header { background: linear-gradient(135deg, #00d4ff, #00ff88); padding: 24px; text-align: center; }
                .header h1 { margin: 0; color: white; font-size: 1.5rem; }
                .header p { margin: 8px 0 0; color: rgba(255,255,255,0.9); font-size: 0.9rem; }
                .content { padding: 24px; }
                .news-item { border-left: 4px solid #00d4ff; padding: 16px; margin-bottom: 16px; background: #f8f9fa; border-radius: 0 8px 8px 0; }
                .news-item.bearish { border-left-color: #ff4757; }
                .news-item.bullish { border-left-color: #00ff88; }
                .ticker { font-size: 1.25rem; font-weight: bold; color: #1a1a2e; margin-bottom: 4px; }
                .headline { font-size: 1rem; color: #333; margin-bottom: 8px; line-height: 1.4; }
                .meta { display: flex; gap: 16px; font-size: 0.85rem; color: #666; margin-bottom: 8px; }
                .sentiment { font-weight: bold; }
                .sentiment.bullish { color: #00b894; }
                .sentiment.bearish { color: #ff4757; }
                .summary { font-size: 0.9rem; color: #555; font-style: italic; }
                .btn { display: inline-block; padding: 10px 20px; background: #00d4ff; color: white; text-decoration: none; border-radius: 6px; margin-top: 8px; }
                .footer { padding: 16px 24px; background: #f8f9fa; text-align: center; font-size: 0.8rem; color: #999; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🚨 NASDAQ News Alert</h1>
                    <p>{timestamp}</p>
                </div>
                <div class="content">
        """

        for item in news_items:
            ticker = item.get("ticker", "UNKNOWN")
            headline = item.get("headline", "No headline")
            source = item.get("source", "Unknown")
            sentiment = item.get("sentiment_score", 0)
            summary = item.get("ai_summary", "")
            url = item.get("url", "#")
            category = item.get("category", "NEWS").upper()

            sentiment_class = "bullish" if sentiment > 0 else "bearish"
            sentiment_icon = "🟢" if sentiment > 0 else "🔴"

            html += f"""
                    <div class="news-item {sentiment_class}">
                        <div class="ticker">{ticker} <span style="font-size: 0.8rem; color: #666;">({category})</span></div>
                        <div class="headline">{headline}</div>
                        <div class="meta">
                            <span>Source: {source}</span>
                            <span class="sentiment {sentiment_class}">{sentiment_icon} Sentiment: {sentiment:+.1f}</span>
                        </div>
                        {f'<div class="summary">💡 {summary}</div>' if summary else ''}
                        <a href="{url}" class="btn" target="_blank">Read Full Article →</a>
                    </div>
            """

        html += """
                </div>
                <div class="footer">
                    NASDAQ News Scraper • AI-Powered Market Intelligence<br>
                    <a href="#">Unsubscribe</a>
                </div>
            </div>
        </body>
        </html>
        """

        timestamp = datetime.now().strftime("%B %d, %Y at %I:%M %p ET")
        return html.format(timestamp=timestamp)

    def format_sms_body(self, news_item: Dict) -> str:
        """Format SMS text (160 char limit consideration)"""
        ticker = news_item.get("ticker", "UNKNOWN")
        headline = news_item.get("headline", "")[:80]  # Truncate
        sentiment = news_item.get("sentiment_score", 0)

        direction = "📈" if sentiment > 0 else "📉"

        return f"""🚨 NASDAQ ALERT: {ticker}

{direction} {headline}{"..." if len(news_item.get("headline", "")) > 80 else ""}

Sentiment: {sentiment:+.0f}

Read: {news_item.get("url", "")[:50]}..."""

    async def send_email(
        self,
        to_email: str,
        news_items: List[Dict]
    ) -> bool:
        """
        Send email notification.
        """
        if not self.sendgrid_client:
            print("SendGrid not configured. Email not sent.")
            return False

        try:
            subject = self.format_email_subject(news_items)
            html_content = self.format_email_body(news_items)

            message = Mail(
                from_email=Email(self.from_email),
                to_emails=To(to_email),
                subject=subject,
                html_content=Content("text/html", html_content)
            )

            response = self.sendgrid_client.send(message)
            success = 200 <= response.status_code < 300

            if success:
                print(f"✅ Email sent to {to_email}")
            else:
                print(f"❌ Email failed: {response.status_code}")

            return success

        except Exception as e:
            print(f"Error sending email: {e}")
            return False

    async def send_sms(
        self,
        to_phone: str,
        news_item: Dict
    ) -> bool:
        """
        Send SMS notification.
        """
        if not self.twilio_client or not self.from_phone:
            print("Twilio not configured. SMS not sent.")
            return False

        try:
            body = self.format_sms_body(news_item)

            message = self.twilio_client.messages.create(
                body=body,
                from_=self.from_phone,
                to=to_phone
            )

            print(f"✅ SMS sent to {to_phone} (SID: {message.sid})")
            return True

        except Exception as e:
            print(f"Error sending SMS: {e}")
            return False

    async def notify_for_news(
        self,
        news_items: List[Dict],
        email_recipients: Optional[List[str]] = None,
        sms_recipients: Optional[List[str]] = None
    ) -> Dict:
        """
        Send notifications for news items that warrant alerts.
        """
        # Filter to only significant items
        alert_items = [item for item in news_items if await self.should_notify(item)]

        if not alert_items:
            return {"notified": False, "reason": "No high-impact items", "items_checked": len(news_items)}

        results = {
            "notified": True,
            "items": len(alert_items),
            "email": {"sent": 0, "failed": 0},
            "sms": {"sent": 0, "failed": 0}
        }

        # Send email (batch all items)
        if email_recipients and self.sendgrid_client:
            for email in email_recipients:
                success = await self.send_email(email, alert_items)
                if success:
                    results["email"]["sent"] += 1
                else:
                    results["email"]["failed"] += 1

        # Send SMS (one per item, max 3 to avoid spam)
        if sms_recipients and self.twilio_client:
            for phone in sms_recipients:
                for item in alert_items[:3]:  # Max 3 SMS per cycle
                    success = await self.send_sms(phone, item)
                    if success:
                        results["sms"]["sent"] += 1
                    else:
                        results["sms"]["failed"] += 1

        return results

    async def send_digest(
        self,
        to_email: str,
        period: str = "daily"
    ) -> bool:
        """
        Send a digest of all high-impact news from the last period.
        Called separately from the scraper.
        """
        # This would query the database for recent high-impact news
        # and send a summary email
        # Implementation depends on database access
        pass


class NotificationConfig:
    """
    Configuration for notifications.
    Load from environment or database.
    """

    @staticmethod
    def get_email_recipients() -> List[str]:
        """Get list of email recipients from env"""
        recipients = os.getenv("NOTIFICATION_EMAIL_RECIPIENTS", "")
        return [e.strip() for e in recipients.split(",") if e.strip()]

    @staticmethod
    def get_sms_recipients() -> List[str]:
        """Get list of phone numbers from env"""
        recipients = os.getenv("NOTIFICATION_SMS_RECIPIENTS", "")
        # Format: +1234567890,+0987654321
        return [p.strip() for p in recipients.split(",") if p.strip()]

    @staticmethod
    def is_enabled() -> bool:
        """Check if notifications are enabled"""
        return os.getenv("ENABLE_NOTIFICATIONS", "true").lower() == "true"


# Simple test
async def test_notifier():
    """Test notification system"""
    notifier = NotificationManager()

    test_news = {
        "ticker": "NVDA",
        "headline": "NVIDIA Announces Record Q4 Revenue, Shares Surge 15%",
        "source": "Yahoo Finance",
        "url": "https://finance.yahoo.com/news/nvidia-earnings",
        "impact_level": "high",
        "sentiment_score": 85,
        "ai_summary": "NVIDIA beat expectations with strong AI chip demand driving growth.",
        "category": "earnings"
    }

    print("Testing notification logic...")
    should_send = await notifier.should_notify(test_news)
    print(f"Should notify: {should_send}")

    if should_send:
        print("\nEmail subject:", notifier.format_email_subject([test_news]))
        print("\nSMS body:")
        print(notifier.format_sms_body(test_news))


if __name__ == "__main__":
    asyncio.run(test_notifier())
