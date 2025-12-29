from src.x.scraper import XScraper

async def test_x_scraper_bookmarks():
    scraper = XScraper.from_env()
    await scraper.get_bookmarks(limit=20)

if __name__ == "__main__":
    import asyncio

    asyncio.run(test_x_scraper_bookmarks())
