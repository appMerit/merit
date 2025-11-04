"""User service with None-handling bugs."""


def get_user_email(user):
    """Get user email - BUG: No None check!"""
    return user.email.lower()


def get_user_profile(user_id):
    """Fetch user profile - BUG: Returns None without checking in caller!"""
    # Simulates database lookup that might return None
    if user_id < 0:
        return None
    return {"id": user_id, "name": "User"}


def format_user_name(user):
    """Format user name - BUG: Assumes user dict has 'name' key!"""
    return user['name'].strip().title()


def get_user_age(user):
    """Get user age - BUG: No validation on None!"""
    return user.get('age') + 1  # age might be None!


def send_notification(user, message):
    """Send notification - BUG: No None checks!"""
    email = user.email
    return f"Sent '{message}' to {email}"

