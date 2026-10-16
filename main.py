"""
Main entry point for MailAgent
"""

import asyncio
import sys
from mailagent.core.agent import EmailAgent
from mailagent.core.config import settings


async def main():
    """Main function"""
    print("MailAgent starting...")
    print(f"Environment: {settings.environment}")
    print(f"Autonomy mode: {settings.default_autonomy_mode}")

    # Initialize agent
    user_id = "default_user"  # This would come from authentication
    agent = EmailAgent(user_id)

    try:
        await agent.initialize()
        print("Agent initialized successfully")

        # Process all accounts
        accounts = await agent.db.get_accounts_by_user(user_id)
        print(f"Found {len(accounts)} email accounts")

        for account in accounts:
            account_id = account["id"]
            print(f"Processing account: {account['email_address']}")
            await agent.process_account(account_id)

        print("Processing complete")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        await agent.shutdown()
        print("Agent shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
