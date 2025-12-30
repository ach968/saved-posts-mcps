from src.x.scraper import XScraper

async def test_x_scraper_search():
    scraper = XScraper.from_env()
    bookmarks = await scraper.get_bookmarks()
    results = scraper.search_bookmarks(bookmarks, "sleep")
    print(f"\nFound {len(results)} posts containing 'sleep':")
    for post in results:
        print(f"  - @{post.author.username}: {post.content[:100]}...")

async def test_x_scraper_fetch():
    import requests

    cookies = {
        'kdt': 'jxG25fjMKZoWirw12FZMfwn7bDeNx0iYmFjove7D',
        'd_prefs': 'MjoxLGNvbnNlbnRfdmVyc2lvbjoyLHRleHRfdmVyc2lvbjoxMDAw',
        '__cuid': 'b9f26e8288e5432088ea4063644ce580',
        'des_opt_in': 'Y',
        'lang': 'en',
        'dnt': '1',
        'guest_id': 'v1%3A176696778813141715',
        'g_state': '{"i_l":0,"i_ll":1766967789916}',
        'auth_token': 'eb39b49c428252c050c35f3f562d74e2179dc263',
        'ct0': 'c237d6b1fb20fe5c7b3f0a46b47c361faeca1b43fc96784cd657ebbff43505bcafedb8b76757b030038d2f6acfd89b5e59044e67f29caa206085769ac5b68d48c473c0c5eeea701c1af255610e6af601',
        'twid': 'u%3D1215489243687968774',
        'guest_id_marketing': 'v1%3A176696778813141715',
        'guest_id_ads': 'v1%3A176696778813141715',
        'personalization_id': '"v1_BwxNNi+/iviHAbXiu2uAOg=="',
        '__cf_bm': 'kM5iyGH5Asqbn__.AbWkR7yOuYRNKXU_bBfs8mqEX8g-1767078462.703261-1.0.1.1-ScLbtjwWg0UK45shhjlXjS.jxP6_iGDKp3NO4Td_tJjyerDEUaM.Ww7gopKc9vFS9H6D0pg2WCrsGWmO1pOX4ZdwEBa4JLr89vsVMmNGhTJRet8Tcq17nc7pDXH6m74S',
    }

    headers = {
        'accept': '*/*',
        'accept-language': 'en-US,en;q=0.5',
        'authorization': 'Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA',
        'content-type': 'application/json',
        'priority': 'u=1, i',
        'referer': 'https://x.com/i/bookmarks',
        'sec-ch-ua': '"Brave";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Linux"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'sec-gpc': '1',
        'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
        'x-client-transaction-id': 'ybPOCwjiN4c8UOGmkuwF2UuiRa3Rqz2OY+nCNzDPkokccQsc2n2FyMYH1MdBuywdqAbfzcyETKRqj3Ztdl9SlOq5Eqs3yg',
        'x-csrf-token': 'c237d6b1fb20fe5c7b3f0a46b47c361faeca1b43fc96784cd657ebbff43505bcafedb8b76757b030038d2f6acfd89b5e59044e67f29caa206085769ac5b68d48c473c0c5eeea701c1af255610e6af601',
        'x-twitter-active-user': 'yes',
        'x-twitter-auth-type': 'OAuth2Session',
        'x-twitter-client-language': 'en',
        'x-xp-forwarded-for': '37c6b90633e814e625d75ae2932be4691890a1df20b2623ece428dcd764bf19129dd8d841c12ef9e8f3eec5c83e118ba380066433c3236cdbadf3c665b35e6f91a2588fad978b680e6e53399a3c1bf7bde70eaae7d81c837470dabc04fd1ed9caeac035646f114e15fa17d7f357306296a99ad0ac78cc696bd307fdfc4b32a4191853293baacd63fe95f1521bdb1467a9c28fdee5df8910426e26ace279049521c3592bfeba675b2522ecfc1c7a29af5fb8bb9edca2d52ee57483884253e105d61d6e69b2cfccf0fd5b71990121681fa26b831a7f3fa0b8beca196595674650e2b7bca843431f7ab860a07735ab63b4866',
        # 'cookie': 'kdt=jxG25fjMKZoWirw12FZMfwn7bDeNx0iYmFjove7D; d_prefs=MjoxLGNvbnNlbnRfdmVyc2lvbjoyLHRleHRfdmVyc2lvbjoxMDAw; __cuid=b9f26e8288e5432088ea4063644ce580; des_opt_in=Y; lang=en; dnt=1; guest_id=v1%3A176696778813141715; g_state={"i_l":0,"i_ll":1766967789916}; auth_token=eb39b49c428252c050c35f3f562d74e2179dc263; ct0=c237d6b1fb20fe5c7b3f0a46b47c361faeca1b43fc96784cd657ebbff43505bcafedb8b76757b030038d2f6acfd89b5e59044e67f29caa206085769ac5b68d48c473c0c5eeea701c1af255610e6af601; twid=u%3D1215489243687968774; guest_id_marketing=v1%3A176696778813141715; guest_id_ads=v1%3A176696778813141715; personalization_id="v1_BwxNNi+/iviHAbXiu2uAOg=="; __cf_bm=kM5iyGH5Asqbn__.AbWkR7yOuYRNKXU_bBfs8mqEX8g-1767078462.703261-1.0.1.1-ScLbtjwWg0UK45shhjlXjS.jxP6_iGDKp3NO4Td_tJjyerDEUaM.Ww7gopKc9vFS9H6D0pg2WCrsGWmO1pOX4ZdwEBa4JLr89vsVMmNGhTJRet8Tcq17nc7pDXH6m74S',
    }

    params = {
        'variables': '{"count":20,"includePromotedContent":true}',
        'features': '{"rweb_video_screen_enabled":false,"profile_label_improvements_pcf_label_in_post_enabled":true,"responsive_web_profile_redirect_enabled":false,"rweb_tipjar_consumption_enabled":true,"verified_phone_label_enabled":false,"creator_subscriptions_tweet_preview_api_enabled":true,"responsive_web_graphql_timeline_navigation_enabled":true,"responsive_web_graphql_skip_user_profile_image_extensions_enabled":false,"premium_content_api_read_enabled":false,"communities_web_enable_tweet_community_results_fetch":true,"c9s_tweet_anatomy_moderator_badge_enabled":true,"responsive_web_grok_analyze_button_fetch_trends_enabled":false,"responsive_web_grok_analyze_post_followups_enabled":true,"responsive_web_jetfuel_frame":true,"responsive_web_grok_share_attachment_enabled":true,"articles_preview_enabled":true,"responsive_web_edit_tweet_api_enabled":true,"graphql_is_translatable_rweb_tweet_is_translatable_enabled":true,"view_counts_everywhere_api_enabled":true,"longform_notetweets_consumption_enabled":true,"responsive_web_twitter_article_tweet_consumption_enabled":true,"tweet_awards_web_tipping_enabled":false,"responsive_web_grok_show_grok_translated_post":true,"responsive_web_grok_analysis_button_from_backend":true,"creator_subscriptions_quote_tweet_preview_enabled":false,"freedom_of_speech_not_reach_fetch_enabled":true,"standardized_nudges_misinfo":true,"tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled":true,"longform_notetweets_rich_text_read_enabled":true,"longform_notetweets_inline_media_enabled":true,"responsive_web_grok_image_annotation_enabled":true,"responsive_web_grok_imagine_annotation_enabled":true,"responsive_web_grok_community_note_auto_translation_is_enabled":false,"responsive_web_enhance_cards_enabled":false}',
    }

    response = requests.get(
        'https://x.com/i/api/graphql/E6jlrZG4703s0mcA9DfNKQ/Bookmarks',
        params=params,
        cookies=cookies,
        headers=headers,
    )

    data = response.json()
    return data

if __name__ == "__main__":
    import asyncio

    asyncio.run(test_x_scraper_search())
    # data = asyncio.run(test_x_scraper_fetch())
    # print(data)