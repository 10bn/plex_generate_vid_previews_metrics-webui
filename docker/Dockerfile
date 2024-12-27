FROM linuxserver/ffmpeg:7.0.1

# Install Python and pip
RUN apt-get update && apt-get install -y \
    mediainfo \
    software-properties-common \
    gcc \
    musl-dev \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy the requirements.txt file to the working directory
COPY requirements.txt .

# Install the Python dependencies
ENV PIP_BREAK_SYSTEM_PACKAGES 1
RUN pip3 install --user -r requirements.txt

# Ensure the Python user base binary directory is in PATH
ENV PATH="/root/.local/bin:${PATH}"

# Copy the Python script and .env file to the working directory
COPY src/plex_generate_previews.py .
COPY config/.env.example .env

# Set environment variables from .env file
RUN pip3 install --user python-dotenv

# Run the Python script when the container starts
ENTRYPOINT ["/bin/bash", "-c", "python3 /app/src/plex_generate_previews.py"]
