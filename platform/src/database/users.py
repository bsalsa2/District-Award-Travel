"""
User database operations and repository pattern.
Handles all database interactions for user profiles.
"""

from typing import Optional, List, Dict, Any
import sqlite3
from datetime import datetime
import logging
from contextlib import contextmanager
import hashlib
import secrets

from ..models.user import User, UserCreate, UserUpdate, UserResponse, UserRole

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class UserRepository:
    """Repository for user CRUD operations"""

    def __init__(self, db_path: str = "platform/data/users.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema"""
        with self._get_db_connection() as conn:
            cursor = conn.cursor()

            # Users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    hashed_password TEXT NOT NULL,
                    first_name TEXT NOT NULL,
                    last_name TEXT NOT NULL,
                    date_of_birth TEXT,
                    role TEXT NOT NULL DEFAULT 'member',
                    is_active INTEGER NOT NULL DEFAULT 1,
                    is_verified INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_login TEXT,
                    metadata TEXT
                )
            """)

            # User preferences table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_preferences (
                    user_id TEXT PRIMARY KEY,
                    theme TEXT NOT NULL DEFAULT 'dark',
                    language TEXT NOT NULL DEFAULT 'en',
                    currency TEXT NOT NULL DEFAULT 'USD',
                    timezone TEXT NOT NULL DEFAULT 'America/New_York',
                    newsletter_opt_in INTEGER NOT NULL DEFAULT 1,
                    marketing_opt_in INTEGER NOT NULL DEFAULT 0,
                    preferred_contact_method TEXT NOT NULL DEFAULT 'email',
                    travel_notifications INTEGER NOT NULL DEFAULT 1,
                    seat_preference TEXT NOT NULL DEFAULT 'window',
                    meal_preference TEXT NOT NULL DEFAULT 'standard',
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            """)

            # Contact info table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS contact_info (
                    user_id TEXT PRIMARY KEY,
                    primary_email TEXT NOT NULL,
                    secondary_email TEXT,
                    phone_number TEXT NOT NULL,
                    secondary_phone TEXT,
                    street_address TEXT NOT NULL,
                    city TEXT NOT NULL,
                    state TEXT NOT NULL,
                    postal_code TEXT NOT NULL,
                    country TEXT NOT NULL,
                    is_primary INTEGER NOT NULL DEFAULT 1,
                    billing_street_address TEXT,
                    billing_city TEXT,
                    billing_state TEXT,
                    billing_postal_code TEXT,
                    billing_country TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            """)

            # Travel profile table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS travel_profile (
                    user_id TEXT PRIMARY KEY,
                    loyalty_tier TEXT NOT NULL DEFAULT 'standard',
                    travel_alerts_enabled INTEGER NOT NULL DEFAULT 1,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            """)

            # Frequent flyer numbers
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS frequent_flyer_numbers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    airline_code TEXT NOT NULL,
                    number TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                    UNIQUE(airline_code, user_id)
                )
            """)

            # Travel documents table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS travel_documents (
                    document_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    document_type TEXT NOT NULL,
                    document_number TEXT NOT NULL,
                    issuing_country TEXT NOT NULL,
                    expiration_date TEXT NOT NULL,
                    first_name TEXT NOT NULL,
                    last_name TEXT NOT NULL,
                    issued_date TEXT,
                    document_image_url TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            """)

            # Indexes for performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_frequent_flyer_user ON frequent_flyer_numbers(user_id)")

            conn.commit()
            logger.info("Database schema initialized successfully")

    @contextmanager
    def _get_db_connection(self):
        """Context manager for database connections"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
            yield conn
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            raise
        finally:
            if conn:
                conn.close()

    def _hash_password(self, password: str) -> str:
        """Hash password using PBKDF2"""
        salt = secrets.token_hex(16)
        key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000
        )
        return f"pbkdf2_sha256${salt}${key.hex()}"

    def _verify_password(self, hashed_password: str, password: str) -> bool:
        """Verify password against hashed password"""
        if not hashed_password.startswith("pbkdf2_sha256$"):
            return False

        parts = hashed_password.split('$')
        if len(parts) != 3:
            return False

        salt = parts[1]
        stored_key = parts[2]

        key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000
        )

        return key.hex() == stored_key

    def create_user(self, user_data: UserCreate) -> UserResponse:
        """Create a new user"""
        hashed_password = self._hash_password(user_data.password)

        with self._get_db_connection() as conn:
            cursor = conn.cursor()

            # Insert user
            cursor.execute("""
                INSERT INTO users (
                    user_id, username, email, hashed_password, first_name, last_name,
                    date_of_birth, role, is_active, is_verified, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(secrets.token_hex(16)),
                user_data.username,
                user_data.email,
                hashed_password,
                user_data.first_name,
                user_data.last_name,
                user_data.date_of_birth.isoformat() if user_data.date_of_birth else None,
                UserRole.MEMBER.value,
                1,
                0,
                datetime.now().isoformat(),
                datetime.now().isoformat()
            ))

            # Insert preferences
            cursor.execute("""
                INSERT INTO user_preferences (
                    user_id, theme, language, currency, timezone, newsletter_opt_in,
                    marketing_opt_in, preferred_contact_method, travel_notifications,
                    seat_preference, meal_preference
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                cursor.lastrowid,
                'dark',
                'en',
                'USD',
                'America/New_York',
                1,
                0,
                'email',
                1,
                'window',
                'standard'
            ))

            # Insert contact info
            cursor.execute("""
                INSERT INTO contact_info (
                    user_id, primary_email, secondary_email, phone_number, secondary_phone,
                    street_address, city, state, postal_code, country, is_primary,
                    billing_street_address, billing_city, billing_state,
                    billing_postal_code, billing_country
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                cursor.lastrowid,
                user_data.contact_info.primary_email,
                user_data.contact_info.secondary_email,
                user_data.contact_info.phone_number,
                user_data.contact_info.secondary_phone,
                user_data.contact_info.address.street_address,
                user_data.contact_info.address.city,
                user_data.contact_info.address.state,
                user_data.contact_info.address.postal_code,
                user_data.contact_info.address.country,
                1,
                user_data.contact_info.billing_address.street_address if user_data.contact_info.billing_address else None,
                user_data.contact_info.billing_address.city if user_data.contact_info.billing_address else None,
                user_data.contact_info.billing_address.state if user_data.contact_info.billing_address else None,
                user_data.contact_info.billing_address.postal_code if user_data.contact_info.billing_address else None,
                user_data.contact_info.billing_address.country if user_data.contact_info.billing_address else None
            ))

            # Insert travel profile
            cursor.execute("""
                INSERT INTO travel_profile (
                    user_id, loyalty_tier, travel_alerts_enabled
                ) VALUES (?, ?, ?)
            """, (
                cursor.lastrowid,
                'standard',
                1
            ))

            conn.commit()

            logger.info(f"User created successfully: {user_data.username}")
            return self.get_user_by_id(cursor.lastrowid)

    def get_user_by_id(self, user_id: str) -> Optional[UserResponse]:
        """Get user by ID"""
        with self._get_db_connection() as conn:
            cursor = conn.cursor()

            # Get user
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            user_row = cursor.fetchone()
            if not user_row:
                return None

            # Get preferences
            cursor.execute("SELECT * FROM user_preferences WHERE user_id = ?", (user_id,))
            preferences_row = cursor.fetchone()

            # Get contact info
            cursor.execute("SELECT * FROM contact_info WHERE user_id = ?", (user_id,))
            contact_row = cursor.fetchone()

            # Get travel profile
            cursor.execute("SELECT * FROM travel_profile WHERE user_id = ?", (user_id,))
            profile_row = cursor.fetchone()

            # Get frequent flyer numbers
            cursor.execute("SELECT airline_code, number FROM frequent_flyer_numbers WHERE user_id = ?", (user_id,))
            frequent_flyer_rows = cursor.fetchall()

            # Get travel documents
            cursor.execute("SELECT * FROM travel_documents WHERE user_id = ?", (user_id,))
            document_rows = cursor.fetchall()

            if not user_row or not preferences_row or not contact_row or not profile_row:
                return None

            user_data = {
                "user_id": user_row["user_id"],
                "username": user_row["username"],
                "email": user_row["email"],
                "hashed_password": user_row["hashed_password"],
                "first_name": user_row["first_name"],
                "last_name": user_row["last_name"],
                "date_of_birth": datetime.fromisoformat(user_row["date_of_birth"]) if user_row["date_of_birth"] else None,
                "role": user_row["role"],
                "is_active": bool(user_row["is_active"]),
                "is_verified": bool(user_row["is_verified"]),
                "created_at": datetime.fromisoformat(user_row["created_at"]),
                "updated_at": datetime.fromisoformat(user_row["updated_at"]),
                "last_login": datetime.fromisoformat(user_row["last_login"]) if user_row["last_login"] else None,
                "preferences": {
                    "theme": preferences_row["theme"],
                    "language": preferences_row["language"],
                    "currency": preferences_row["currency"],
                    "timezone": preferences_row["timezone"],
                    "newsletter_opt_in": bool(preferences_row["newsletter_opt_in"]),
                    "marketing_opt_in": bool(preferences_row["marketing_opt_in"]),
                    "preferred_contact_method": preferences_row["preferred_contact_method"],
                    "travel_notifications": bool(preferences_row["travel_notifications"]),
                    "seat_preference": preferences_row["seat_preference"],
                    "meal_preference": preferences_row["meal_preference"],
                    "loyalty_program_priority": []
                },
                "contact_info": {
                    "primary_email": contact_row["primary_email"],
                    "secondary_email": contact_row["secondary_email"],
                    "phone_number": contact_row["phone_number"],
                    "secondary_phone": contact_row["secondary_phone"],
                    "address": {
                        "street_address": contact_row["street_address"],
                        "city": contact_row["city"],
                        "state": contact_row["state"],
                        "postal_code": contact_row["postal_code"],
                        "country": contact_row["country"],
                        "is_primary": bool(contact_row["is_primary"])
                    },
                    "billing_address": {
                        "street_address": contact_row["billing_street_address"],
                        "city": contact_row["billing_city"],
                        "state": contact_row["billing_state"],
                        "postal_code": contact_row["billing_postal_code"],
                        "country": contact_row["billing_country"]
                    } if contact_row["billing_street_address"] else None
                },
                "travel_profile": {
                    "frequent_flyer_numbers": {row["airline_code"]: row["number"] for row in frequent_flyer_rows},
                    "hotel_program_numbers": {},
                    "car_rental_numbers": {},
                    "passport_number": None,
                    "known_traveler_number": None,
                    "redress_number": None,
                    "frequent_traveler_status": {},
                    "preferred_airlines": [],
                    "preferred_hotels": [],
                    "preferred_car_rental": [],
                    "loyalty_tier": profile_row["loyalty_tier"],
                    "travel_alerts_enabled": bool(profile_row["travel_alerts_enabled"])
                },
                "travel_documents": [],
                "metadata": {}
            }

            # Get travel documents
            for doc_row in document_rows:
                user_data["travel_documents"].append({
                    "document_type": doc_row["document_type"],
                    "document_number": doc_row["document_number"],
                    "issuing_country": doc_row["issuing_country"],
                    "expiration_date": datetime.fromisoformat(doc_row["expiration_date"]),
                    "first_name": doc_row["first_name"],
                    "last_name": doc_row["last_name"],
                    "issued_date": datetime.fromisoformat(doc_row["issued_date"]) if doc_row["issued_date"] else None,
                    "document_image_url": doc_row["document_image_url"]
                })

            return UserResponse(**user_data)

    def get_user_by_email(self, email: str) -> Optional[UserResponse]:
        """Get user by email"""
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM users WHERE email = ?", (email,))
            user_row = cursor.fetchone()
            if user_row:
                return self.get_user_by_id(user_row["user_id"])
            return None

    def get_user_by_username(self, username: str) -> Optional[UserResponse]:
        """Get user by username"""
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM users WHERE username = ?", (username,))
            user_row = cursor.fetchone()
            if user_row:
                return self.get_user_by_id(user_row["user_id"])
            return None

    def update_user(self, user_id: str, update_data: UserUpdate) -> Optional[UserResponse]:
        """Update user information"""
        with self._get_db_connection() as conn:
            cursor = conn.cursor()

            # Update user table
            updates = []
            params = []

            if update_data.first_name is not None:
                updates.append("first_name = ?")
                params.append(update_data.first_name)

            if update_data.last_name is not None:
                updates.append("last_name = ?")
                params.append(update_data.last_name)

            if update_data.email is not None:
                updates.append("email = ?")
                params.append(update_data.email)

            if update_data.date_of_birth is not None:
                updates.append("date_of_birth = ?")
                params.append(update_data.date_of_birth.isoformat())

            if update_data.is_active is not None:
                updates.append("is_active = ?")
                params.append(int(update_data.is_active))

            if updates:
                updates.append("updated_at = ?")
                params.append(datetime.now().isoformat())
                params.append(user_id)

                query = f"UPDATE users SET {', '.join(updates)} WHERE user_id = ?"
                cursor.execute(query, params)

            # Update preferences if provided
            if update_data.preferences is not None:
                pref_updates = []
                pref_params = []

                if update_data.preferences.theme is not None:
                    pref_updates.append("theme = ?")
                    pref_params.append(update_data.preferences.theme)

                if update_data.preferences.language is not None:
                    pref_updates.append("language = ?")
                    pref_params.append(update_data.preferences.language)

                if update_data.preferences.currency is not None:
                    pref_updates.append("currency = ?")
                    pref_params.append(update_data.preferences.currency)

                if update_data.preferences.timezone is not None:
                    pref_updates.append("timezone = ?")
                    pref_params.append(update_data.preferences.timezone)

                if update_data.preferences.newsletter_opt_in is not None:
                    pref_updates.append("newsletter_opt_in = ?")
                    pref_params.append(int(update_data.preferences.newsletter_opt_in))

                if update_data.preferences.marketing_opt_in is not None:
                    pref_updates.append("marketing_opt_in = ?")
                    pref_params.append(int(update_data.preferences.marketing_opt_in))

                if update_data.preferences.preferred_contact_method is not None:
                    pref_updates.append("preferred_contact_method = ?")
                    pref_params.append(update_data.preferences.preferred_contact_method)

                if update_data.preferences.travel_notifications is not None:
                    pref_updates.append("travel_notifications = ?")
                    pref_params.append(int(update_data.preferences.travel_notifications))

                if update_data.preferences.seat_preference is not None:
                    pref_updates.append("seat_preference = ?")
                    pref_params.append(update_data.preferences.seat_preference)

                if update_data.preferences.meal_preference is not None:
                    pref_updates.append("meal_preference = ?")
                    pref_params.append(update_data.preferences.meal_preference)

                if pref_updates:
                    pref_params.append(user_id)
                    query = f"UPDATE user_preferences SET {', '.join(pref_updates)} WHERE user_id = ?"
                    cursor.execute(query, pref_params)

            # Update contact info if provided
            if update_data.contact_info is not None:
                contact_updates = []
                contact_params = []

                if update_data.contact_info.primary_email is not None:
                    contact_updates.append("primary_email = ?")
                    contact_params.append(update_data.contact_info.primary_email)

                if update_data.contact_info.secondary_email is not None:
                    contact_updates.append("secondary_email = ?")
                    contact_params.append(update_data.contact_info.secondary_email)

                if update_data.contact_info.phone_number is not None:
                    contact_updates.append("phone_number = ?")
                    contact_params.append(update_data.contact_info.phone_number)

                if update_data.contact_info.secondary_phone is not None:
                    contact_updates.append("secondary_phone = ?")
                    contact_params.append(update_data.contact_info.secondary_phone)

                if update_data.contact_info.address is not None:
                    contact_updates.append("street_address = ?")
                    contact_params.append(update_data.contact_info.address.street_address)
                    contact_updates.append("city = ?")
                    contact_params.append(update_data.contact_info.address.city)
                    contact_updates.append("state = ?")
                    contact_params.append(update_data.contact_info.address.state)
                    contact_updates.append("postal_code = ?")
                    contact_params.append(update_data.contact_info.address.postal_code)
                    contact_updates.append("country = ?")
                    contact_params.append(update_data.contact_info.address.country)

                if update_data.contact_info.billing_address is not None:
                    contact_updates.append("billing_street_address = ?")
                    contact_params.append(update_data.contact_info.billing_address.street_address)
                    contact_updates.append("billing_city = ?")
                    contact_params.append(update_data.contact_info.billing_address.city)
                    contact_updates.append("billing_state = ?")
                    contact_params.append(update_data.contact_info.billing_address.state)
                    contact_updates.append("billing_postal_code = ?")
                    contact_params.append(update_data.contact_info.billing_address.postal_code)
                    contact_updates.append("billing_country = ?")
                    contact_params.append(update_data.contact_info.billing_address.country)

                if contact_updates:
                    contact_params.append(user_id)
                    query = f"UPDATE contact_info SET {', '.join(contact_updates)} WHERE user_id = ?"
                    cursor.execute(query, contact_params)

            # Update travel profile if provided
            if update_data.travel_profile is not None:
                profile_updates = []
                profile_params = []

                if update_data.travel_profile.loyalty_tier is not None:
                    profile_updates.append("loyalty_tier = ?")
                    profile_params.append(update_data.travel_profile.loyalty_tier)

                if update_data.travel_profile.travel_alerts_enabled is not None:
                    profile_updates.append("travel_alerts_enabled = ?")
                    profile_params.append(int(update_data.travel_profile.travel_alerts_enabled))

                if profile_updates:
                    profile_params.append(user_id)
                    query = f"UPDATE travel_profile SET {', '.join(profile_updates)} WHERE user_id = ?"
                    cursor.execute(query, profile_params)

            conn.commit()
            logger.info(f"User updated successfully: {user_id}")
            return self.get_user_by_id(user_id)

    def add_frequent_flyer_number(self, user_id: str, airline_code: str, number: str) -> bool:
        """Add frequent flyer number for user"""
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO frequent_flyer_numbers
                    (user_id, airline_code, number) VALUES (?, ?, ?)
                """, (user_id, airline_code, number))
                conn.commit()
                logger.info(f"Added frequent flyer number for user {user_id}: {airline_code} - {number}")
                return True
            except sqlite3.Error as e:
                logger.error(f"Error adding frequent flyer number: {e}")
                return False

    def add_travel_document(self, user_id: str, document_data: Dict[str, Any]) -> bool:
        """Add travel document for user"""
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO travel_documents (
                        document_id, user_id, document_type, document_number,
                        issuing_country, expiration_date, first_name, last_name,
                        issued_date, document_image_url
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(secrets.token_hex(16)),
                    user_id,
                    document_data["document_type"],
                    document_data["document_number"],
                    document_data["issuing_country"],
                    document_data["expiration_date"].isoformat(),
                    document_data["first_name"],
                    document_data["last_name"],
                    document_data["issued_date"].isoformat() if document_data.get("issued_date") else None,
                    document_data.get("document_image_url")
                ))
                conn.commit()
                logger.info(f"Added travel document for user {user_id}")
                return True
            except sqlite3.Error as e:
                logger.error(f"Error adding travel document: {e}")
                return False

    def verify_user(self, user_id: str) -> bool:
        """Mark user as verified"""
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users SET is_verified = 1, updated_at = ? WHERE user_id = ?
            """, (datetime.now().isoformat(), user_id))
            conn.commit()
            logger.info(f"User verified: {user_id}")
            return cursor.rowcount > 0

    def authenticate_user(self, username: str, password: str) -> Optional[UserResponse]:
        """Authenticate user"""
        user = self.get_user_by_username(username)
        if not user:
            return None

        if not self._verify_password(user.hashed_password, password):
            return None

        # Update last login
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users SET last_login = ? WHERE user_id = ?
            """, (datetime.now().isoformat(), user.user_id))
            conn.commit()

        logger.info(f"User authenticated: {username}")
        return user

    def search_users(self, query: str, limit: int = 100) -> List[UserResponse]:
        """Search users by name or email"""
        with self._get_db_connection() as conn:
            cursor = conn.cursor()

            search_term = f"%{query}%"
            cursor.execute("""
                SELECT user_id FROM users
                WHERE username LIKE ? OR email LIKE ? OR first_name LIKE ? OR last_name LIKE ?
                LIMIT ?
            """, (search_term, search_term, search_term, search_term, limit))

            user_ids = [row["user_id"] for row in cursor.fetchall()]
            return [self.get_user_by_id(uid) for uid in user_ids if self.get_user_by_id(uid)]

    def get_all_users(self, limit: int = 1000, offset: int = 0) -> List[UserResponse]:
        """Get all users with pagination"""
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT user_id FROM users
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, (limit, offset))

            user_ids = [row["user_id"] for row in cursor.fetchall()]
            return [self.get_user_by_id(uid) for uid in user_ids if self.get_user_by_id(uid)]

    def count_users(self) -> int:
        """Count total users"""
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM users")
            return cursor.fetchone()["count"]
