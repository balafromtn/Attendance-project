# Use an official Python runtime
FROM python:3.9-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file
COPY requirements.txt requirements.txt

# Install the Python dependencies
RUN pip install -r requirements.txt

# Copy the rest of the backend code into the container
COPY . .

# Tell Docker what command to run when the container starts
# We use 'flask run --host=0.0.0.0' to make it accessible
CMD ["flask", "run", "--host=0.0.0.0"]