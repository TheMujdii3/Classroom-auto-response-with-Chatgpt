from openai import OpenAI
import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

SCOPES = [
    'https://www.googleapis.com/auth/classroom.courses',
    'https://www.googleapis.com/auth/classroom.coursework.me',
    'https://www.googleapis.com/auth/classroom.coursework.students',
    'https://www.googleapis.com/auth/classroom.courseworkmaterials',
    'https://www.googleapis.com/auth/classroom.student-submissions.students.readonly',
    'https://www.googleapis.com/auth/drive.file',
]

TOKEN_DIR = './'
client = OpenAI(
    api_key="your openai key")
OpenAI.api_key = 'your openai key'


def get_classroom_service(email, creds_json_path='credentials.json'):
   
    # Path to the token file for this specific user
    token_file_path = os.path.join(TOKEN_DIR, f'{email}_token.json')

    creds = None

    # Check if the token file exists
    if os.path.exists(token_file_path):
        # Load credentials from the token file
        creds = Credentials.from_authorized_user_file(token_file_path, SCOPES)
    else:
        # If token file doesn't exist, go through OAuth flow and save the token
        flow = InstalledAppFlow.from_client_secrets_file(creds_json_path, SCOPES)
        creds = flow.run_local_server(port=0)

        # Save the new token to a file for this user
        with open(token_file_path, 'w') as token_file:
            token_file.write(creds.to_json())

    # Build and return the Google Classroom API service
    service = build('classroom', 'v1', credentials=creds)

    return service


def get_drive_service(creds_json_path='credentials.json'):
  
    flow = InstalledAppFlow.from_client_secrets_file(creds_json_path, SCOPES)
    creds = flow.run_local_server(port=0)
    service = build('drive', 'v3', credentials=creds)
    return service


def get_latest_assignment(service):
    """Fetch the latest assignment for the user from all courses."""

    # Fetch the list of courses for the user
    courses_result = service.courses().list().execute()
    courses = courses_result.get('courses', [])

    if not courses:
        print('No courses found.')
        return None

    # Loop through each course to fetch the latest assignment
    latest_assignment = None
    for course in courses:
        course_id = course['id']
        course_name = course['name']

        print(f"Fetching assignments for course: {course_name} (ID: {course_id})")

        # Fetch the latest assignment from this course
        results = service.courses().courseWork().list(courseId=course_id, orderBy='dueDate desc', pageSize=1).execute()
        assignments = results.get('courseWork', [])

        if assignments:
            # Get the first assignment (since it's ordered by due date)
            assignment = assignments[0]
            assignment_title = assignment['title']
            assignment_description = assignment.get('description', 'No description available.')

            print(f"Latest assignment in {course_name}: {assignment_title} - {assignment_description}")

            # Return the first assignment found
            latest_assignment = assignment
            break  # Stop after finding the first assignment

    if not latest_assignment:
        print('No assignments found across all courses.')

    return latest_assignment


def create_text_file(file_path, content):
    """Creates a text file with the specified content."""
    try:
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(content)
        print(f"File created: {file_path}")
    except IOError as error:
        print(f"An error occurred while creating the file: {error}")


def update_submission_grade(service, course_id, coursework_id, submission_id, draft_grade=None):
    """Update a student's submission with a grade or draft grade."""

    # Prepare the update body
    update_body = {}
    if draft_grade is not None:
        update_body["draftGrade"] = draft_grade

    try:
        # Update the submission with draftGrade
        service.courses().courseWork().studentSubmissions().patch(
            courseId=course_id,
            courseWorkId=coursework_id,
            id=submission_id,
            body=update_body,
            updateMask='draftGrade'
        ).execute()

        print(f"Updated submission with draft grade: {draft_grade}")

    except HttpError as error:
        print(f"An error occurred while updating the submission: {error}")


def upload_file_to_drive(service, file_path, mime_type):
    """Uploads a file to Google Drive and returns the file ID."""
    try:
        file_metadata = {
            'name': os.path.basename(file_path),
            'mimeType': mime_type
        }
        media = MediaFileUpload(file_path, mimetype=mime_type)
        file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        print(f"Uploaded file with ID: {file['id']}")
        return file['id']
    except HttpError as error:
        print(f"An error occurred while uploading the file: {error}")
        return None


def update_submission_with_file(service, course_id, coursework_id, submission_id, file_id):
    """Update a student's submission with a file attachment."""

    # Prepare the update body without attachments
    update_body = {
        "state": "RETURNED",  # Ensure the submission is returned to enable updating
        # Other fields like "draftGrade" can be added here if needed
    }

    try:
        # Update the submission state
        service.courses().courseWork().studentSubmissions().patch(
            courseId=course_id,
            courseWorkId=coursework_id,
            id=submission_id,
            body=update_body,
            updateMask='state'
        ).execute()

        print(f"Updated submission state to RETURNED.")

        # Add the file attachment
        # This might need a separate process depending on API capabilities

    except HttpError as error:
        print(f"An error occurred while updating the submission: {error}")


def submit_file_as_student(service, course_id, coursework_id, submission_id, file_id):
    """Submit a file as student work and mark it as TURNED_IN."""

    # Prepare the submission body with the file attachment
    submission_body = {
        "state": "TURNED_IN",  # Mark the submission as turned in
        "attachments": [
            {
                "driveFile": {
                    "id": file_id
                }
            }
        ]
    }

    try:

        # Update the submission with the file attachment


        # Use the turnIn method to officially submit the work
        service.courses().courseWork().studentSubmissions().turnIn(
            courseId=course_id,
            courseWorkId=coursework_id,
            id=submission_id
        ).execute()

        print(f"Submission turned in successfully.")

    except HttpError as error:
        print(f"An error occurred while submitting the file: {error}")


def process_users(email_list):
    for email in email_list:
        print(f"Processing assignments for {email}...")

        # Authenticate the user and initialize Google Classroom and Drive API
        classroom_service = get_classroom_service(email)
        drive_service = get_drive_service()

        # Fetch the latest assignment
        latest_assignment = get_latest_assignment(classroom_service)

        if latest_assignment:
            assignment_title = latest_assignment['title']
            assignment_description = latest_assignment.get('description', 'No description available.')
            course_id = latest_assignment['courseId']
            coursework_id = latest_assignment['id']

            print(f"Latest assignment for {email}: {assignment_title} - {assignment_description}")

            # Generate an AI response based on the assignment description
            completion = client.completions.create(
                model="gpt-3.5-turbo-instruct",
                prompt=assignment_description,
                max_tokens=20,
                n=1
            )
            ai_response = completion.choices[0].text.strip()

            print(f"AI response for {email}: {ai_response}")

            # Create a text file with the AI response
            file_path = 'response.txt'
            create_text_file(file_path, ai_response)

            # Upload the text file to Google Drive
            file_id = upload_file_to_drive(drive_service, file_path, 'text/plain')
            if file_id:
                # Get the student's submission for the assignment
                submissions_result = classroom_service.courses().courseWork().studentSubmissions().list(
                    courseId=course_id,
                    courseWorkId=coursework_id
                ).execute()

                submissions = submissions_result.get('studentSubmissions', [])
                if submissions:
                    submission_id = submissions[0]['id']

                    # Submit the file as student work
                    submit_file_as_student(classroom_service, course_id, coursework_id, submission_id, file_id)
                else:
                    print(f"No submissions found for assignment {assignment_title}")
        else:
            print(f"No assignments found for {email}.")






# Example email list
email_list = ['andreineculai70@gmail.com']
#made by th3mujd11 now only me and god know what i ve dont here in a month probably only god will know what this code does:))
# Run the processing for all users in the email list
if __name__ == '__main__':
    process_users(email_list)
