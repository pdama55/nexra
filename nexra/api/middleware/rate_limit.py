# Rate limiting is implemented in api/dependencies.py via check_rate_limit().
# Called inside get_authenticated_org() on every authenticated request.
# This file reserved for future standalone rate limit middleware if needed.
