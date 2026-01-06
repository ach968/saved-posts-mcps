from src.reddit.scraper import RedditScraper

async def test_reddit_scraper_search():
    scraper = RedditScraper.from_env()
    saved = await scraper.get_saved()
    print(f"\nFetched {len(saved)} saved items")

    # Test fuzzy search with list of queries
    results = scraper.search_saved(saved, ["python"])
    print(f"\nFound {len(results)} posts containing 'python':")
    for post in results[:10]:
        print(f"  - r/{post.metadata.get('subreddit', '?')} @{post.author.username}: {post.content[:80]}...")

    # Test fuzzy matching (typo tolerance)
    results_fuzzy = scraper.search_saved(saved, ["pythn"], fuzzy_threshold=2)
    print(f"\nFuzzy search 'pythn' found {len(results_fuzzy)} posts")

    # Test multiple queries with AND
    results_and = scraper.search_saved(saved, ["the", "and"], match_all=True)
    print(f"\nAND search ['the', 'and'] found {len(results_and)} posts")

    # Test multiple queries with OR
    results_or = scraper.search_saved(saved, ["python", "rust"], match_all=False)
    print(f"\nOR search ['python', 'rust'] found {len(results_or)} posts")

if __name__ == "__main__":
    import asyncio

    asyncio.run(test_reddit_scraper_search())
