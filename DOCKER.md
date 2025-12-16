# Docker Deployment Guide

## Prerequisites
- Docker installed on your system
- Docker Compose installed
- Supabase PostgreSQL connection string

## Quick Start

### 1. Setup Environment Variables

Copy the example environment file and edit it with your credentials:

```bash
cp .env.example .env
```

Edit `.env` file and add your Supabase connection string:

```env
SQLALCHEMY_DATABASE_URI=postgresql://postgres:[YOUR-PASSWORD]@db.[YOUR-PROJECT-REF].supabase.co:5432/postgres
SECRET_KEY=your-generated-secret-key
```

**Generate a secure SECRET_KEY:**
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 2. Build and Run with Docker Compose

```bash
# Build the Docker image
docker-compose build

# Start the application
docker-compose up -d

# View logs
docker-compose logs -f
```

The application will be available at `http://localhost:5000`

### 3. Initialize Database (First Time Only)

If you need to create tables in your Supabase database:

```bash
docker-compose exec web python init_db.py
```

## Docker Commands

### Start the application
```bash
docker-compose up -d
```

### Stop the application
```bash
docker-compose down
```

### View logs
```bash
docker-compose logs -f web
```

### Restart the application
```bash
docker-compose restart
```

### Rebuild the image (after code changes)
```bash
docker-compose build --no-cache
docker-compose up -d
```

### Access the container shell
```bash
docker-compose exec web bash
```

## Using Dockerfile Only (Without Docker Compose)

### Build the image
```bash
docker build -t invoice-maker .
```

### Run the container
```bash
docker run -d \
  --name invoice-maker-app \
  -p 5000:5000 \
  -e SQLALCHEMY_DATABASE_URI="your-supabase-connection-string" \
  -e SECRET_KEY="your-secret-key" \
  invoice-maker
```

### Stop and remove container
```bash
docker stop invoice-maker-app
docker rm invoice-maker-app
```

## Production Deployment

### Environment Variables

For production, ensure you:
1. Use a strong SECRET_KEY
2. Use SSL-enabled database connection string
3. Set proper firewall rules
4. Use a reverse proxy (nginx) in front of the application

### Scaling

To run multiple workers:

```yaml
# In docker-compose.yml, modify the CMD or scale:
docker-compose up -d --scale web=3
```

### Reverse Proxy with Nginx (Optional)

Add this to `docker-compose.yml`:

```yaml
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - web
```

## Troubleshooting

### Container won't start
```bash
# Check logs
docker-compose logs web

# Check if port 5000 is already in use
docker-compose down
docker-compose up
```

### Database connection issues
- Verify your Supabase connection string
- Ensure your IP is allowed in Supabase settings
- Check if the database user has proper permissions

### Permission issues with assets folder
```bash
# Fix permissions
docker-compose exec web chown -R www-data:www-data /app/assets
```

## Health Check

Check if the application is running:
```bash
curl http://localhost:5000/
```

## Backup

The assets folder is mounted as a volume, so your uploaded files persist outside the container.

## Updates

To update the application:

```bash
git pull
docker-compose build
docker-compose up -d
```
