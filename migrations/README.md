# Database Migrations

This directory contains database migration files for the Tubesavely project.

## Files

- `init_database.sql`: Initial database schema creation

## How to Run

You can run the migrations using the MySQL command line tool:

```bash
# Using MySQL client
mysql -u root -p < migrations/init_database.sql

# Or using Docker
docker exec -i mysql mysql -uroot -p{your_password} < migrations/init_database.sql
```

## Migration Naming Convention

Migration files should be named with a prefix of a 3-digit number followed by a descriptive name:

- 001_init_database.sql
- 002_add_user_preferences.sql
- 003_modify_download_status.sql

This ensures migrations are executed in the correct order.
