import re
from typing import Dict, List, Optional, Set
import logging
from datetime import datetime
import json
from notion_client import Client


def normalize_phone(phone: str) -> Set[str]:
    """
    Normalize phone numbers into a consistent format.
    Returns a set of possible matches since one Notion entry might have multiple numbers.

    Example inputs:
    - +17344476348
    - +1 647-334-1872
    - +1 587-817-0076 ::: +1 587-714-2836
    - 790-35
    - Empty/None
    """
    if not phone:
        logging.debug(f"normalize_phone: Empty input")
        return set()

    numbers = set()
    logging.debug(f"normalize_phone: Processing input '{phone}'")

    # Split on potential separators
    for potential_number in re.split(r"[:::\n,;]", phone):
        # Strip whitespace
        number = potential_number.strip()
        if not number:
            continue

        logging.debug(f"normalize_phone: Processing part '{number}'")

        # Remove all non-digit characters except +
        clean = re.sub(r"[^\d+]", "", number)
        logging.debug(f"normalize_phone: After cleaning '{clean}'")

        normalized = None

        # Handle different formats
        if clean.startswith("+1"):
            normalized = clean  # Already in full format
        elif clean.startswith("1"):
            normalized = f"+{clean}"  # Add + to full number
        elif len(clean) == 10 and clean.isdigit():
            normalized = f"+1{clean}"  # Add +1 to 10-digit number
        elif len(clean) >= 5:  # Ignore very short numbers
            normalized = clean  # Keep as-is for manual review

        if normalized:
            logging.debug(f"normalize_phone: Adding normalized number '{normalized}'")
            numbers.add(normalized)

    logging.debug(f"normalize_phone: Final set of numbers: {numbers}")
    return numbers


class NotionSync:
    def __init__(self, database_id: str, notion_token: str):
        self.database_id = database_id
        logging.debug(f"Initializing NotionSync with database_id: {database_id}")
        self.client = Client(auth=notion_token)

    def fetch_contacts(self) -> Dict[str, dict]:
        """
        Fetch all contacts from Notion database.
        Returns dict mapping normalized phone numbers to Notion page IDs and other data.
        """
        contacts = {}
        has_more = True
        next_cursor = None

        logging.debug("Starting Notion contact fetch")

        try:
            # First, verify database access and structure
            database = self.client.databases.retrieve(self.database_id)
            logging.debug(
                f"Successfully connected to database: {database.get('title', [{}])[0].get('text', {}).get('content', 'Unnamed')}"
            )

            # Log available properties
            properties = database.get("properties", {})
            logging.debug(
                f"Available properties in database: {list(properties.keys())}"
            )

            while has_more:
                logging.debug(f"Querying database with cursor: {next_cursor}")

                response = self.client.databases.query(
                    database_id=self.database_id,
                    start_cursor=next_cursor,
                    page_size=100,
                )

                logging.debug(f"Received {len(response['results'])} results")

                for page in response["results"]:
                    props = page["properties"]
                    logging.debug(
                        f"Processing page {page['id']} with properties: {list(props.keys())}"
                    )

                    # Get all phone numbers
                    phone_numbers = set()
                    for field in ["Primary Phone", "Secondary Phone"]:
                        if field in props:
                            prop = props[field]
                            logging.debug(f"Found {field} property: {prop}")

                            # Check for phone_number property type and value
                            if prop["type"] == "phone_number" and prop["phone_number"]:
                                raw_number = prop["phone_number"]
                                logging.debug(
                                    f"Processing Notion contact phone from {field}: {raw_number}"
                                )
                                numbers = normalize_phone(raw_number)
                                phone_numbers.update(numbers)
                                logging.debug(
                                    f"Normalized numbers for {field}: {numbers}"
                                )

                    if not phone_numbers:
                        logging.debug(
                            f"No valid phone numbers found for page {page['id']}"
                        )
                        continue

                    # Get name from title property
                    name = "Unknown"
                    for prop_name, prop in props.items():
                        if prop["type"] == "title" and prop["title"]:
                            name = prop["title"][0]["text"]["content"]
                            logging.debug(f"Found contact name: {name}")
                            break

                    # Store contact info for each phone number
                    contact_info = {
                        "page_id": page["id"],
                        "name": name,
                        "all_numbers": phone_numbers,
                    }

                    for number in phone_numbers:
                        contacts[number] = contact_info
                        logging.debug(
                            f"Stored Notion contact {name} with number {number}"
                        )

                has_more = response.get("has_more", False)
                next_cursor = response.get("next_cursor")
                logging.debug(
                    f"Pagination: has_more={has_more}, next_cursor={next_cursor}"
                )

        except Exception as e:
            logging.error(f"Error fetching Notion contacts: {str(e)}", exc_info=True)
            return {}

        logging.info(f"Fetched {len(contacts)} contacts from Notion")
        logging.debug(f"All Notion contact numbers: {list(contacts.keys())}")
        return contacts

    def update_contact(
        self, page_id: str, last_contact: datetime, recent_messages: List[dict] = None
    ) -> bool:
        """Update a Notion contact with latest communication data"""

        # Prepare recent messages summary if available
        messages_summary = ""
        if recent_messages:
            try:
                processed_messages = []
                for msg in recent_messages:
                    # Handle string messages that need to be parsed
                    if isinstance(msg, str):
                        try:
                            msg = json.loads(msg)
                        except json.JSONDecodeError:
                            logging.warning(f"Failed to parse message JSON: {msg}")
                            continue

                    # Validate message structure
                    if not isinstance(msg, dict):
                        logging.warning(f"Invalid message format: {msg}")
                        continue

                    msg_type = msg.get("type")
                    msg_body = msg.get("body")

                    if msg_type is not None and msg_body is not None:
                        direction = "→" if msg_type == 2 else "←"
                        processed_messages.append(f"{direction} {msg_body[:100]}...")
                    else:
                        logging.warning(f"Message missing required fields: {msg}")

                messages_summary = "\n".join(processed_messages)
                logging.debug(f"Processed messages summary: {messages_summary}")

            except Exception as e:
                logging.error(f"Error processing messages: {e}")
                messages_summary = "Error processing messages"

        properties = {"Last Contacted": {"date": {"start": last_contact.isoformat()}}}

        if messages_summary:
            properties["Recent Messages"] = {
                "rich_text": [{"type": "text", "text": {"content": messages_summary}}]
            }

        try:
            self.client.pages.update(page_id=page_id, properties=properties)
            return True
        except Exception as e:
            logging.error(f"Failed to update Notion contact {page_id}: {e}")
            return False


def sync_contacts_to_notion(conn, notion: NotionSync):
    """
    Sync contact data from SQLite to Notion
    """
    cursor = conn.cursor()

    # Get all contact summaries
    cursor.execute("""
        SELECT 
            address,
            last_message_timestamp,
            last_call_timestamp,
            recent_messages
        FROM contact_summaries
    """)

    # Fetch Notion contacts
    notion_contacts = notion.fetch_contacts()

    updates = 0
    not_found = 0

    for address, last_msg, last_call, messages in cursor.fetchall():
        logging.debug(f"Processing SQLite contact with address: {address}")

        # Get latest contact timestamp
        last_contact = max(
            datetime.fromisoformat(ts) for ts in [last_msg, last_call] if ts is not None
        )

        # Try to find matching Notion contact
        normalized = normalize_phone(address)
        logging.debug(f"Normalized SQLite address {address} to {normalized}")

        contact = None
        for number in normalized:
            if number in notion_contacts:
                contact = notion_contacts[number]
                logging.debug(
                    f"Found matching Notion contact for {number}: {contact['name']}"
                )
                break
            else:
                logging.debug(f"No match found for {number} in Notion contacts")

        if contact:
            # Update Notion
            recent_msgs = []
            if messages:
                recent_msgs = [
                    json.loads(msg) if isinstance(msg, str) else msg
                    for msg in json.loads(messages)
                ]

            success = notion.update_contact(
                contact["page_id"], last_contact, recent_msgs
            )

            if success:
                updates += 1
                logging.info(f"Updated Notion contact {contact['name']} ({address})")
            else:
                not_found += 1
                logging.warning(f"Failed to update contact {address}")
        else:
            not_found += 1
            logging.info(f"No matching Notion contact found for {address}")
            logging.debug("Available Notion numbers for comparison:")
            for notion_number in notion_contacts.keys():
                logging.debug(f"  {notion_number}")

    return updates, not_found
