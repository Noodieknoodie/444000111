# README_MODERN_DEV.md

Cheat Sheet: Modern SQLite & FastAPI App Development
Database is located in backend/data/401k_payments_master.db
SQLite Data Types & Time Handling
Dynamic Typing (Type Affinity): SQLite doesn’t enforce column types rigidly. The declared type of a column is just a preference (affinity) – any column can store any type of value​
. For example, there’s no dedicated BOOLEAN type; use integer 0/1 (SQLite treats TRUE/FALSE as 1/0)​
.
No Native DATE/TIME Type: SQLite has no separate storage class for dates/times​
. Store dates as one of:
TEXT (ISO8601 string: "YYYY-MM-DD HH:MM:SS"),
INTEGER (Unix timestamp in seconds), or
REAL (Julian day number)​
.
Conventional practice: use ISO8601 TEXT for human-readable dates – these compare correctly as strings when zero-padded​
. For example, '2024-03-01' > '2023-12-31' evaluates true because the strings are in chronological order.
Date/Time Functions: Leverage SQLite’s built-in date and time functions for calculations and filtering. Use DATE(), TIME(), DATETIME(), or STRFTIME() to convert or compare dates. For example:
sql
Copy code
-- Get records in the last 30 days
SELECT * 
FROM Events 
WHERE EventDate >= date('now','-30 days');
This uses date('now','-30 days') to compute a cutoff date 30 days ago​
. Similarly, you can add intervals (e.g. '+7 days') or truncate times ('start of month' modifiers). Storing timestamps as UTC and using 'now' (UTC) ensures consistency.
Grouping by Date: Use strftime to group or format dates. For example, to aggregate by month:
sql
Copy code
SELECT STRFTIME('%Y-%m', EventDate) AS year_month, COUNT(*) 
FROM Events 
GROUP BY STRFTIME('%Y-%m', EventDate);
This groups records by year-month (e.g. "2025-03")​
LEARNSQL.COM
.
Strict Mode (New in SQLite 3.37+): If you need rigid types, SQLite supports “STRICT” tables (since 2021) that enforce type checking​
. This is optional – by default, SQLite’s flexible typing is a feature, not a bug​
.
SQLite Views for Business Logic
What is a View? A view is a stored SQL query that you can treat like a virtual table. Define a view to encapsulate complex joins or calculations:
sql
Copy code
CREATE VIEW ActiveUsers AS 
  SELECT u.id, u.name, u.last_login 
  FROM users u 
  WHERE u.last_login > date('now','-30 days');
This creates a view ActiveUsers representing users active in the last 30 days. Query it with normal SELECTs (SELECT * FROM ActiveUsers;).
Encapsulate Logic: Using views centralizes business logic in the database. Instead of duplicating filters or joins across many queries, define them once in a view. Your code can simply select from the view, improving consistency and maintainability. If the logic changes, update the view definition rather than every query in your code.
Read-Only Nature: SQLite views are essentially read-only by default – they are not materialized or stored as data, and you cannot INSERT/UPDATE/DELETE directly on a view​
. The view’s result is computed on demand each time you query it​
. (If you need to make a view writable, you can create INSTEAD OF triggers, but this is advanced usage​
.)
Performance: Selecting from a view is almost the same as running its underlying query. SQLite’s query planner inlines (flattens) the view’s SELECT into the outer query​
. In practice, a view doesn’t add runtime cost; it just saves you from rewriting SQL. In fact, using views can slightly reduce overhead by reusing a prepared query plan rather than reparsing SQL text each time​
. Just ensure proper indexes exist on underlying tables, as the view itself cannot be indexed separately.
Best Practice: Use views to keep Python code minimal – push heavy filtering or calculation into SQL. For example, a view can calculate a “full_name” or an “active” flag, so your Python code doesn’t have to recompute it. This separation keeps logic in one place (the DB), aligning with the DRY principle.
Python <-> SQLite (sqlite3) Patterns
Use Direct Queries (No ORM): Python’s built-in sqlite3 module is lightweight and efficient for local apps. You don’t need an ORM for a small project – you can execute SQL directly. For example:
python
Copy code
import sqlite3
conn = sqlite3.connect("app.db")
conn.row_factory = sqlite3.Row            # optional: to get dict-like rows&#8203;:contentReference[oaicite:14]{index=14}  
with conn:  # context manager ensures commit or rollback&#8203;:contentReference[oaicite:15]{index=15}&#8203;:contentReference[oaicite:16]{index=16}  
    # READ: query the ActiveUsers view
    for row in conn.execute("SELECT id, name FROM ActiveUsers"):
        print(row["id"], row["name"])     # sqlite3.Row allows name-based access&#8203;:contentReference[oaicite:17]{index=17}  
    # WRITE: parameterized insert
    conn.execute(
        "INSERT INTO logs(event_type, msg) VALUES(?, ?)", 
        ("login", "User logged in")
    )
Explanation: Using with conn: wraps operations in a transaction, auto-committing on success or rolling back if an error occurs​
. The row_factory is set so that fetched rows behave like dictionaries (accessible by column name)​
. You can iterate directly over conn.execute(...) which returns an iterable cursor​
​
 – no need to call fetchall() unless you need a list.
Avoid Creating Multiple Cursors Unnecessarily: You usually don’t need to manually create cursor objects (conn.cursor()) – the connection can execute queries directly and will return a cursor if needed​
. For most simple uses, just call conn.execute or conn.executemany and iterate over results.
Parameter Binding: Do use SQL parameters (the ? placeholder) to insert Python variables into queries​
. This not only prevents SQL injection but also handles data types properly. For example: conn.execute("SELECT * FROM users WHERE name = ?", (username,)). Avoid Python string formatting or f-strings to concatenate SQL – e.g. "...WHERE name = '%s'" % username – this is unsafe and error-prone​
. (SQLite will treat an unquoted %s literally if you do it wrong, or worse, allow injection.) Always let the sqlite3 driver handle binding.
Bulk Operations: Use executemany() for batch inserts/updates. For example, to insert many rows:
python
Copy code
data = [(1, "Alice"), (2, "Bob"), ...]  
conn.executemany("INSERT INTO users(id, name) VALUES(?, ?)", data)
This sends all inserts in one call, which is much faster than looping over execute for each row​
​
.
Keep SQL DRY: If the same SQL snippet is used in multiple places (e.g. a complex WHERE clause), factor it out. Options: define a view (as discussed) or at least store the query in one Python function or constant. This prevents mistakes and makes maintenance easier if the logic changes. Example: Instead of writing the same join across several endpoints, create a view for that join. In code, call SELECT * FROM that_view everywhere – one source of truth.
Connections and Scope: Reuse the database connection if possible (especially for multiple operations in one request) to avoid the overhead of opening/closing connections repeatedly. In a FastAPI app, you might create a single sqlite3.connect per request (or use a global connection if thread-safe with check_same_thread=False). Ensure to commit transactions (with conn: or conn.commit()) so changes persist.
Row Access Patterns: The default fetch returns tuples. For clarity, you can use sqlite3.Row as shown, or even define a custom row factory to get dicts​
 or namedtuples. This makes code more readable (access row['column_name'] instead of row[0], etc.). It’s especially handy when mapping to Pydantic models by unpacking the dict (e.g. MyModel(**row)).
Pydantic for Data Validation & Serialization
Define Pydantic Models for DB Data: Use Pydantic’s BaseModel to create classes that mirror the structure of your data. This provides type validation and easy serialization. For example:
python
Copy code
from pydantic import BaseModel
from datetime import datetime
class UserOut(BaseModel):
    id: int
    name: str
    last_login: datetime
    is_active: bool
If you fetch a row from SQLite (where last_login might be stored as text and is_active as 0/1), you can convert it: user = UserOut(**row). Pydantic will validate types and even parse types for you. A string like "2025-03-01 12:00:00" will be parsed into a datetime object​
DOCS.PYDANTIC.DEV
, and an integer 0/1 will be converted to a boolean for is_active (0 -> False, 1 -> True). If the data doesn’t conform (e.g. a non-numeric string in an int field), Pydantic raises a clear error.
Use Enums for Coded Values: If your SQLite data uses codes or flags (e.g. an integer status code), you can define a Python Enum and use it in your Pydantic model. Pydantic will accept the raw value and convert it. For example:
python
Copy code
from enum import IntEnum
class Status(IntEnum):
    DRAFT = 0
    FINAL = 1
class Report(BaseModel):
    status: Status
Now if a DB row has status = 1, creating Report(status=1) will give Report.status == Status.FINAL​
DOCS.PYDANTIC.DEV
. This makes your code more expressive (using Status.FINAL instead of magic number 1) while still easily accepting DB data. (Tip:) By default Pydantic will output the enum value as its name or value depending on config – you can set model_config = {"use_enum_values": True} in Pydantic v2 (or Config.use_enum_values = True in v1) if you want the JSON serialization to use the raw value.
Validation and Security: Pydantic ensures the data your API returns (or accepts) conforms to the schema. This is especially useful when reading from SQLite, since SQLite’s dynamic types might give you surprises (e.g. a number where you expected a string). By validating with Pydantic, you catch issues early. It also helps to prevent accidentally exposing fields you didn’t intend to include in a response, because your Pydantic model will explicitly list the fields to serialize.
Serialization: Pydantic models can be easily serialized to JSON. FastAPI uses them to generate response JSON automatically, but you can also call my_model.json() or my_model.dict() to get serializable forms. Pydantic knows how to serialize common Python types (e.g. datetime -> ISO 8601 string)​
DOCS.PYDANTIC.DEV
. When a Pydantic model is returned by FastAPI, any datetime fields will be output as ISO8601 timestamp strings, enums as their values, etc., which is exactly what a frontend (Next.js/React) can consume.
Using orm_mode (optional): If you ever use an ORM or even if you have a class with attributes, Pydantic can parse those with model_config = {"from_attributes": True} in v2 (or Config.orm_mode = True in v1). But since we are using direct SQLite and likely dealing with dicts/tuples, you can just pass the dict to the model.
FastAPI Patterns with SQLite & Pydantic
Reading from DB in Endpoints: In your FastAPI path functions, query the SQLite database and map the results to Pydantic models for the response. FastAPI will automatically serialize the Pydantic models to JSON. For example:
python
Copy code
@app.get("/users/", response_model=list[UserOut])
def list_users():
    conn = sqlite3.connect("app.db")
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT id, name, last_login, active as is_active FROM ActiveUsers").fetchall()
    users = [UserOut(**row) for row in rows]
    return users
Here response_model=list[UserOut] tells FastAPI and documentation that the response is a list of UserOut objects. FastAPI uses this to validate and filter the output data to match the model​
. You can actually return plain dicts (or sqlite3.Row mappings) and FastAPI would convert them to UserOut as well, but returning Pydantic models (or dataclasses) is convenient. In the above, we alias the SQL active field to is_active to match our Pydantic model field name.
Response Models & Filtering: The response_model parameter ensures that even if you return extra fields, they will be filtered out. It’s a good practice to always set a response model. FastAPI will document the API using it and also “convert and filter the output data to its type declaration”​
. This means your clients (Next.js front-end) get data in the exact shape defined by the model, with proper types (e.g. strings, numbers) in JSON.
CORS (Connecting to Next.js): If your FastAPI backend is separate from your Next.js frontend (different origin/port), you must enable CORS so the browser can call the API. Use Starlette’s CORSMiddleware:
python
Copy code
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Frontend origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
This configuration permits the React/Next.js app at localhost:3000 to access your API​
. Adjust origins/ports as needed. Without this, the browser will block cross-origin requests.
Integrating with Next.js/React: Design your FastAPI endpoints to deliver data that the frontend can use directly. Usually this means JSON responses that map cleanly to your front-end state or props. Using the patterns above (Pydantic models and response_model), your API will naturally return JSON that can be fetched by Next.js (using fetch or libraries like SWR/Axios). For example, a Next.js page might call /users/ and get an array of {id, name, last_login, is_active} objects – directly usable in the UI. Aim to keep your API responses lightweight: don’t send huge blobs of data if the frontend only needs a few fields (again, Pydantic models help select only what’s needed).
File Uploads: FastAPI makes handling file uploads straightforward and efficient. Use UploadFile in your endpoint to receive a file without loading it fully into memory. For example:
python
Copy code
@app.post("/upload/")
async def upload_file(file: UploadFile = File(...)):
    upload_path = f"uploads/{file.filename}"
    with open(upload_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)  # save in chunks&#8203;:contentReference[oaicite:34]{index=34}
    return {"filename": file.filename}
Here, UploadFile provides a file-like object (file.file) which we copy to a destination on disk. Using shutil.copyfileobj reads in chunks internally (1MB by default)​
​
, so you can handle large files without consuming too much RAM. Always close the file (FastAPI/Starlette will close file.file when the request is done, or you can call file.file.close() explicitly)​
. By streaming the file to disk, this approach is reliable even for big uploads. Avoid reading the entire file with file.file.read() unless you know it’s small, as that can exhaust memory for large uploads.
Serving Files/Attachments: If your app needs to return file data (images, PDFs, etc.) to the frontend, use fastapi.responses.FileResponse or StreamingResponse. For example, to let users download an uploaded file:
python
Copy code
from fastapi import responses
@app.get("/files/{filename}")
def get_file(filename: str):
    return responses.FileResponse(f"uploads/{filename}", media_type="application/octet-stream", filename=filename)
This will prompt a download in the browser. Ensure the media_type is correct (e.g. "image/png" for images, etc.).
FastAPI + SQLite Concurrency: FastAPI can handle many requests, but SQLite allows only one writer at a time. For a small app this is usually fine (writes are fast). If you expect many concurrent writes, consider using SQLite’s WAL mode (via PRAGMA journal_mode=WAL;) for better read/write concurrency, and ensure each request uses its own connection (SQLite connections are not inherently thread-safe). For simple cases, sequential writes won’t be an issue. For heavy read loads, SQLite can handle concurrent reads well.
Common Mistakes & Anti-Patterns (Avoid These!)
Assuming Rigid Types in SQLite: Don’t expect SQLite to enforce types on its own. For instance, declaring a column as DATE or BOOLEAN does not guarantee format or type – it’s stored as TEXT or INTEGER under the hood. Always validate or format data yourself. Use Pydantic or CHECK constraints (if needed) to ensure values are as expected. In modern SQLite, you can use STRICT tables for type enforcement​
, but in standard operation, remember that "123" could be inserted into an INTEGER column (SQLite will store it as integer 123 if possible, or as text otherwise).
Misusing Date/Time: A common error is inserting dates in a non-ISO format and then failing to query them properly. For example, "03/20/2025" as a date string won’t compare correctly lexicographically. Stick to "YYYY-MM-DD HH:MM:SS" if storing as text​
. Another mistake is forgetting that date('now') is UTC by default – if you insert local time strings and compare to 'now', you might get surprises. It’s best to store UTC timestamps and convert to local time in the application/UI if needed.
Duplicating Logic in Code: Don’t repeat business logic in multiple places. If a certain filter (say “user is active”) is used in several queries, avoid copying that condition everywhere (and risk one instance getting out of sync). Instead, define it once – e.g. as a view or a utility function that all queries use. Similarly, avoid doing in Python what the database can do more efficiently. Example: fetching all rows and then filtering in Python is worse than adding a WHERE clause to your SQL query (databases are optimized for filtering and will use indexes, etc.). Let SQLite do the set-based operations; your Python code should just handle the result.
Bypassing Parameterization: Building SQL query strings by concatenation (especially with user input) is dangerous. This can lead to SQL injection vulnerabilities and bugs. Always use the parameter substitution (?) provided by sqlite3​
. It not only secures your app but also handles quoting for you. Even for constants, parameter binding is a good habit (and sometimes SQLite can cache the query plan for parameterized queries, improving performance on repeated executions).
Inefficient Query Patterns: A few things to avoid for performance and cleanliness:
N+1 Query Problem: Don’t issue a new database query inside a loop for each record if you can combine them. For example, avoid fetching a list of users and then inside that loop querying another table for each user’s details. Use JOINs or subqueries to fetch related data in one go. SQLite can handle reasonably complex joins quickly if indexed properly.
Over-fetching Data: Don’t SELECT * if you don’t need all columns – it wastes memory and bandwidth. Select only the fields you need, especially if some columns are large (e.g. BLOBs or long text).
Not Using Indexes: Ensure you create indexes on columns that you frequently filter or join on (except the ones already PRIMARY KEY which are indexed). SQLite performance on a small scale is fine, but as data grows, lack of indexes on common query patterns will slow things down.
Poor API Practices for Frontend: A few anti-patterns when integrating with a React/Next frontend:
Not handling CORS: as mentioned, forgetting to enable CORS will stop your frontend from calling the API.
Returning raw SQL rows: If you return SQLite row objects or other non-JSON-serializable data, the client will get nothing useful. Always convert to JSON (FastAPI + Pydantic does this for you).
Overcomplicating data for the frontend: The frontend should ideally receive data ready to use. If the frontend needs to calculate something from the data, consider moving that calculation to the backend (either in the SQL query/view or in the response construction). For instance, if the frontend needs an “age” from a birthdate, you could send age in the JSON response (calculated via SQL DATEDIFF or Python) to avoid duplicating that logic in JavaScript.
File Handling Blunders: When dealing with file uploads/downloads:
Don’t read huge files into memory in one go – use streaming (as shown with UploadFile and shutil).
Don’t forget to secure file paths if you allow user-specified filenames (to prevent path traversal attacks). FastAPI’s UploadFile.filename is user-supplied; sanitize or use your own naming scheme for storage.
If storing files, consider the implications: large files in SQLite (BLOBs) can bloat the DB and make backups heavy – often it’s better to store file paths in the DB instead of the file content, unless you need transactions on file data.
Ignoring Error Handling: SQLite operations can fail (unique constraint violations, etc.). Make sure to catch exceptions (sqlite3.IntegrityError, etc.) and handle them – e.g., return a 400 response if a duplicate record insert was attempted. FastAPI will return a 500 error by default if an exception bubbles up. It’s better to catch predictable errors and respond with a clear message or HTTP status.
Not Keeping SQLite Up-to-Date: Finally, ensure your environment uses a modern SQLite version (SQLite improves continuously). Features like JSON functions, window functions, common table expressions (CTEs), etc., are available in recent SQLite and can be very useful for a local app. If you’re using the system SQLite on older OS, it might be outdated. Consider bundling SQLite with your app or using Python’s updated pysqlite (the sqlite3 that comes with Python 3.11+ is usually up-to-date with recent SQLite features).
By following these guidelines – leveraging SQLite’s strengths (simple deployment, fast reads, flexible types) and combining it with Python’s and FastAPI’s tooling (Pydantic for validation, clear API design) – you can build a maintainable, efficient local app. This cheat sheet should help an AI coding assistant (or any developer) recall the key patterns: use SQLite for what it’s good at (set operations, persistence), keep logic DRY with views, use Pydantic models to validate and shape data, and expose clean APIs to the frontend. Happy coding! Do’s and Don’ts Summary:
👍 Do This (Best Practices)	🚫 Avoid This (Anti-Patterns)
Use ISO 8601 date strings or Unix timestamps in SQLite, and use SQLite date functions for filtering​
.	Expecting SQLite to enforce a DATE type or storing dates in ambiguous formats (e.g. "DD/MM/YY").
Leverage views to encapsulate complex queries and business logic (select from the view in code) for consistency and reusability.	Copy-pasting the same SQL logic (joins, filters) in multiple queries or implementing it in Python when the DB could do it.
Use sqlite3 with parameterized queries (? placeholders) for inserts/filters​
.	Building SQL query strings via string concatenation or f-strings (SQL injection risk, harder to maintain)​
.
Fetch and iterate with named cursors or Row for clarity​
 (e.g. row['col']).	Using low-level tuple access for query results everywhere, which makes code hard to read (row[5] without context).
Wrap DB calls in transactions (use with conn:) to auto-commit on success​
.	Manually calling commit() every time (or forgetting to commit at all), and not handling rollbacks on error.
Define Pydantic models for request/response schemas to validate data and serialize output easily.	Returning raw database types (datetime, Decimal, etc.) or unvalidated data directly in FastAPI responses.
Use Enums/booleans in Pydantic to represent status flags or choices (Pydantic will map int/string to Enum)​
DOCS.PYDANTIC.DEV
.	Scattering “magic numbers” or strings in your code for status flags, or letting the frontend interpret raw codes without context.
Use FastAPI’s response_model to enforce output schema and let FastAPI handle conversion​
.	Omitting response models and returning Python dicts/lists without validation (could expose fields or types you didn’t intend).
Enable CORS with CORSMiddleware when frontend is separate​
.	Disabling CORS entirely or forgetting it (the app will work in docs/curly but fail when the frontend calls it).
Handle file uploads with UploadFile, saving in chunks to avoid memory issues​
.	Using bytes for file uploads or reading the entire file at once into memory (bad for large files).
Index your database on frequently queried columns, use WAL for concurrent access if needed.	Neglecting indexes (leading to slow queries) or trying to use SQLite like a high-concurrency server DB without tuning (it’s fast for local use, but has limits).