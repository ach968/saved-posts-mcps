from src.reddit.scraper import RedditScraper

async def test_reddit_scraper_search():
    scraper = RedditScraper.from_env()
    saved = await scraper.get_saved()
    print(f"\nFetched {len(saved)} saved items")

    results = scraper.search_saved(saved, "python")
    print(f"\nFound {len(results)} posts containing 'python':")
    for post in results[:10]:
        print(f"  - r/{post.metadata.get('subreddit', '?')} @{post.author.username}: {post.content[:80]}...")

if __name__ == "__main__":
    import asyncio

    asyncio.run(test_reddit_scraper_search())
