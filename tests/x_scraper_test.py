from src.x.scraper import XScraper

async def test_x_scraper_search():
    scraper = XScraper.from_env()
    bookmarks = await scraper.get_bookmarks()
    results = scraper.search_bookmarks(bookmarks, "sleep")
    print(f"\nFound {len(results)} posts containing 'sleep':")
    for post in results:
        print(f"  - @{post.author.username}: {post.content[:100]}...")

if __name__ == "__main__":
    import asyncio

    asyncio.run(test_x_scraper_search())
