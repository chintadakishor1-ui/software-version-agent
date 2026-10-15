import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types


load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise ValueError("GEMINI_API_KEY not found. Please check your .env file.")


client = genai.Client(api_key=API_KEY)


def get_author(path: str) -> str:
    """Find author information in a local text file."""

    file_path = Path(path)

    if not file_path.is_file():
        return "File not found."

    try:
        content = file_path.read_text(
            encoding="utf-8",
            errors="replace"
        )

        for line in content.splitlines():
            line = line.strip()

            if line.lower().startswith("author:"):
                author = line.split(":", 1)[1].strip()

                if author:
                    return f"Author information found: {author}"

        return "No author information found in the file."

    except OSError:
        return "Could not read this file."


get_author_declaration = {
    "name": "get_author",
    "description": (
        "Read a local text file and find a line beginning "
        "with 'Author:'. Use this tool to find author information."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "path": {
                "type": "STRING",
                "description": "Path of the local text file."
            }
        },
        "required": ["path"]
    }
}


tool = types.Tool(
    function_declarations=[get_author_declaration]
)


def ask_gemini(question: str) -> str:

    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=question,
        config=types.GenerateContentConfig(
            tools=[tool]
        )
    )

    if not response.candidates:
        return "Gemini did not return a response."

    for part in response.candidates[0].content.parts:

        if part.function_call:

            function_call = part.function_call

            if function_call.name == "get_author":

                arguments = dict(function_call.args)

                result = get_author(
                    path=arguments["path"]
                )

                return result

    if response.text:
        return response.text

    return "Gemini did not return a text answer."


if __name__ == "__main__":

    print("Gemini Custom Tool Agent")
    print("------------------------")

    question = input("Ask a question about a local text file: ")

    answer = ask_gemini(question)

    print("\nAgent Answer:")
    print(answer)