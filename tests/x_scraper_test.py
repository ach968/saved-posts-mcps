from src.x.scraper import XScraper

async def test_x_scraper_search():
    scraper = XScraper.from_env()
    bookmarks = await scraper.get_bookmarks()

    # Test fuzzy search with list of queries
    results = scraper.search_bookmarks(bookmarks, ["sleep"])
    print(f"\nFound {len(results)} posts containing 'sleep':")
    for post in results:
        print(f"  - @{post.author.username}: {post.content[:100]}...")

    # Test fuzzy matching (typo tolerance)
    results_fuzzy = scraper.search_bookmarks(bookmarks, ["slepe"], fuzzy_threshold=2)
    print(f"\nFuzzy search 'slepe' found {len(results_fuzzy)} posts")

    # Test multiple queries with AND
    results_and = scraper.search_bookmarks(bookmarks, ["the", "and"], match_all=True)
    print(f"\nAND search ['the', 'and'] found {len(results_and)} posts")

    # Test multiple queries with OR
    results_or = scraper.search_bookmarks(bookmarks, ["sleep", "dream"], match_all=False)
    print(f"\nOR search ['sleep', 'dream'] found {len(results_or)} posts")

if __name__ == "__main__":
    import asyncio

    asyncio.run(test_x_scraper_search())