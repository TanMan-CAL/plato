import asyncio
import json
import logging
import os
from typing import List, Dict, Any

from scrapybara import Scrapybara
from undetected_playwright.async_api import async_playwright
SCRAPYBARA_API_KEY = scrapy-91794c99-4e15-4f9f-bcb0-aecafc8bd166


# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def get_scrapybara_browser():
    """Creates a browser instance on a Scrapybara machine"""
    api_key = os.getenv("SCRAPYBARA_API_KEY")
    if not api_key:
        raise ValueError("SCRAPYBARA_API_KEY environment variable not set")
    
    client = Scrapybara(api_key=api_key)
    instance = client.start_browser()
    logger.info("Scrapybara browser instance started")
    return instance

async def retrieve_menu_items(instance, start_url: str) -> List[Dict[str, Any]]:
    """
    Navigates to the given URL and collects detailed data for each menu item.
    
    Args:
        instance: the scrapybara instance to use
        start_url: the initial url to navigate to
    
    Returns:
        A list of menu items, each represented as a dictionary
    """
    cdp_url = instance.get_cdp_url().cdp_url
    logger.info(f"Connecting to browser using CDP URL: {cdp_url}")
    
    menu_items = []
    
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(cdp_url)
        context = await browser.new_context()
        
        # Enable network request interception to capture GraphQL responses
        page = await context.new_page()
        
        # Set up request interception for GraphQL responses
        async def handle_response(response):
            if "graphql/itemPage?operation=itemPage" in response.url:
                try:
                    response_json = await response.json()
                    # Extract the relevant item data from the GraphQL response
                    if response_json.get("data") and response_json["data"].get("itemPage"):
                        item_data = response_json["data"]["itemPage"]
                        menu_items.append(item_data)
                        logger.info(f"Captured menu item: {item_data.get('name', 'Unknown')}")
                except Exception as e:
                    logger.error(f"Error processing response: {str(e)}")
        
        page.on("response", handle_response)
        
        # Navigate to the restaurant page
        logger.info(f"Navigating to {start_url}")
        await page.goto(start_url)
        
        # Wait for the page to load fully
        await page.wait_for_load_state("networkidle")
        
        # Accept cookies if the dialog appears
        try:
            accept_button = page.locator('button:has-text("Accept All")')
            if await accept_button.is_visible(timeout=5000):
                await accept_button.click()
                logger.info("Accepted cookies dialog")
        except Exception:
            logger.info("No cookies dialog found or failed to accept")
        
        # Scroll down to load all menu sections
        logger.info("Scrolling to load all menu sections")
        await page.evaluate("""
            () => {
                window.scrollTo(0, document.body.scrollHeight);
            }
        """)
        await page.wait_for_timeout(2000)  # Wait for any lazy-loaded content
        
        # Find all menu item cards
        menu_item_cards = page.locator('[data-anchor-id^="MenuItem"]')
        count = await menu_item_cards.count()
        logger.info(f"Found {count} menu item cards")
        
        # Click on each menu item to trigger the GraphQL request
        for i in range(count):
            try:
                # Get a fresh reference to avoid stale elements
                card = page.locator('[data-anchor-id^="MenuItem"]').nth(i)
                
                # Scroll the item into view
                await card.scroll_into_view_if_needed()
                await page.wait_for_timeout(500)  # Small delay for stability
                
                # Click to open the item details
                await card.click()
                logger.info(f"Clicked on menu item {i+1}/{count}")
                
                # Wait for the GraphQL request to complete
                await page.wait_for_timeout(1000)
                
                # Close the item details modal
                close_button = page.locator('button[aria-label="Close"]').first
                await close_button.click()
                await page.wait_for_timeout(500)  # Small delay between actions
                
            except Exception as e:
                logger.error(f"Error processing menu item {i+1}: {str(e)}")
        
        logger.info(f"Collected data for {len(menu_items)} menu items")
        return menu_items

async def main():
    """Main function to run the scraper"""
    try:
        instance = await get_scrapybara_browser()
        logger.info("Starting menu item retrieval")
        
        menu_items = await retrieve_menu_items(
            instance,
            "https://www.doordash.com/store/panda-express-san-francisco-980938/12722988/?event_type=autocomplete&pickup=false",
        )
        
        # Save results to a JSON file
        with open("menu_items.json", "w") as f:
            json.dump(menu_items, f, indent=2)
        
        logger.info(f"Successfully saved {len(menu_items)} menu items to menu_items.json")
        
    except Exception as e:
        logger.error(f"Error in main function: {str(e)}")
    finally:
        # Be sure to close the browser instance after you're done!
        if 'instance' in locals():
            instance.stop()
            logger.info("Scrapybara browser instance stopped")

if __name__ == "__main__":
    asyncio.run(main())