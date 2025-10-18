# Docker Setup Guide for PBPK MCP with ospsuite

## Prerequisites
✅ Docker Desktop is installed and running (confirmed)
✅ R is installed locally (R 4.2.3)
✅ .NET 8 is installed (8.0.120)
✅ Updated Dockerfile with R and ospsuite

## Step 1: Build the Docker Image

Run this command in your terminal (it will take 5-10 minutes):

```bash
docker build --pull --tag mcp-bridge .
```

**What this does:**
- Pulls Python 3.11 slim base image
- Installs R and all required dependencies
- Installs .NET 8 SDK (required by ospsuite's rSharp dependency)
- Installs ospsuite R package from GitHub
- Installs Python MCP bridge application
- Sets up environment variables for R and ospsuite

**Expected output:**
You'll see many lines showing package installations. Key milestones:
1. Installing system dependencies
2. Installing .NET 8
3. Installing R packages (remotes, then ospsuite)
4. Verifying ospsuite installation
5. Building Python application

## Step 2: Verify the Build

After the build completes, verify the image was created:

```bash
docker images | grep mcp-bridge
```

You should see output like:
```
mcp-bridge    latest    <image-id>    <time>    <size>
```

## Step 3: Test the Container

### Quick Test (No Environment File)
```bash
docker run --rm -p 8000:8000 mcp-bridge
```

### With Environment Variables
```bash
docker run --rm -p 8000:8000 --env-file .env mcp-bridge
```

**The container should start and show:**
```
INFO:     Started server process [1]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

## Step 4: Verify ospsuite is Working

In a new terminal, test the health endpoint:

```bash
curl http://localhost:8000/health
```

**Expected response should include:**
```json
{
  "status": "healthy",
  "r_environment": {
    "available": true,
    "r_version": "4.x.x",
    "r_path": "/usr/bin/R",
    "r_home": "/usr/lib/R",
    "ospsuite_version": "12.3.2",
    "ospsuite_library_path": "/usr/local/lib/R/site-library"
  }
}
```

## Step 5: Test a Simulation (Optional)

Test the simulation endpoint:

```bash
curl -X POST http://localhost:8000/api/v1/simulation/run \
  -H "Content-Type: application/json" \
  -d '{
    "model_file": "tests/fixtures/demo.pkml",
    "parameters": {}
  }'
```

## Troubleshooting

### Build Fails with .NET Error
If you see errors about .NET not being found during the build:
- The Dockerfile installs .NET 8 for Debian 12
- Check if the Microsoft package repository URL is correct
- Try adding `--no-cache` to the docker build command

### Build Fails with ospsuite Error
If ospsuite installation fails:
- Check the GitHub repository is accessible
- Verify .NET is properly installed in the container
- Look for specific error messages about missing dependencies

### Container Starts but Health Check Fails
If the container runs but `/health` shows `available: false`:
- Check the R_PATH and R_HOME environment variables
- Verify ospsuite was installed in the correct location
- Look at container logs: `docker logs <container-id>`

### Can't Connect to Container
If you can't reach http://localhost:8000:
- Ensure port 8000 isn't already in use: `lsof -i :8000`
- Check the container is running: `docker ps`
- Verify port mapping is correct in the docker run command

## Making Changes

If you need to modify the Dockerfile:

1. Make your changes to `Dockerfile`
2. Rebuild the image:
   ```bash
   docker build --no-cache --tag mcp-bridge .
   ```
3. Test the new image

## Using with Make

Once Docker is responsive, you can use the Makefile shortcuts:

```bash
# Build image
make build-image

# Run container
make run-image
```

## Next Steps

Once you have a working container with ospsuite:

1. ✅ Container builds successfully
2. ✅ Health endpoint shows ospsuite is available
3. 🔄 Ready to implement Task 3.3: Replace mock adapter with real ospsuite calls
4. 🔄 Test actual PBPK simulations

## Environment Variables

The `.env` file has been created with these R-related variables:

```bash
R_PATH=/usr/local/bin/R                    # Local Mac path (not used in container)
R_HOME=/Library/Frameworks/R.framework/Resources  # Local Mac path (not used in container)
ADAPTER_TIMEOUT_SECONDS=10
```

**Inside the container**, these are set differently in the Dockerfile:
```bash
ENV R_PATH=/usr/bin/R
ENV R_HOME=/usr/lib/R
ENV OSPSUITE_LIBS=/usr/local/lib/R/site-library
# Optional: additional directories inside the container where `.pkml` files are allowed
ENV MCP_MODEL_SEARCH_PATHS=/app/tests/fixtures
```

## Summary

You now have:
- ✅ Updated Dockerfile with R, .NET, and ospsuite
- ✅ `.env` file configured
- ✅ Docker Desktop running
- 📝 Complete setup instructions
- 🚀 Ready to build and test!

Run `docker build --pull --tag mcp-bridge .` in your terminal to start!
