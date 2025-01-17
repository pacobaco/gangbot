from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import os

app = Flask(__name__)

# Configure the database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///bidding_system.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Database models
class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False)
    deadline = db.Column(db.DateTime, nullable=False)
    criteria = db.Column(db.String(50), nullable=False)  # e.g., "lowest price", "fastest completion"
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Bid(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)
    bidder = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    completion_time = db.Column(db.Integer, nullable=False)  # In hours or days
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)

# Initialize the database
with app.app_context():
    db.create_all()

# Helper function to find task by ID
def find_task(task_id):
    return Task.query.get(task_id)

# Route to create a new task
@app.route('/tasks', methods=['POST'])
def create_task():
    data = request.json
    deadline = datetime.strptime(data['deadline'], "%Y-%m-%d %H:%M:%S")
    task = Task(
        title=data['title'],
        description=data['description'],
        deadline=deadline,
        criteria=data['criteria']
    )
    db.session.add(task)
    db.session.commit()
    return jsonify({"message": "Task created successfully!", "task": {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "deadline": task.deadline,
        "criteria": task.criteria
    }}), 201

# Route to view all tasks
@app.route('/tasks', methods=['GET'])
def get_tasks():
    tasks_list = Task.query.all()
    tasks = [
        {
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "deadline": task.deadline,
            "criteria": task.criteria,
            "created_at": task.created_at
        } for task in tasks_list
    ]
    return jsonify(tasks)

# Route to submit a bid for a task
@app.route('/tasks/<int:task_id>/bids', methods=['POST'])
def submit_bid(task_id):
    task = find_task(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404

    data = request.json
    bid = Bid(
        task_id=task.id,
        bidder=data['bidder'],
        price=data['price'],
        completion_time=data['completion_time']  # In hours or days
    )
    db.session.add(bid)
    db.session.commit()
    return jsonify({"message": "Bid submitted successfully!", "bid": {
        "id": bid.id,
        "task_id": bid.task_id,
        "bidder": bid.bidder,
        "price": bid.price,
        "completion_time": bid.completion_time
    }}), 201

# Route to evaluate bids and select a winner
@app.route('/tasks/<int:task_id>/evaluate', methods=['POST'])
def evaluate_bids(task_id):
    task = find_task(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404

    task_bids = Bid.query.filter_by(task_id=task_id).all()
    if not task_bids:
        return jsonify({"error": "No bids found for this task"}), 404

    # Evaluation logic
    criteria = task.criteria
    if criteria == "lowest price":
        winner = min(task_bids, key=lambda x: x.price)
    elif criteria == "fastest completion":
        winner = min(task_bids, key=lambda x: x.completion_time)
    else:
        return jsonify({"error": "Unknown evaluation criteria"}), 400

    return jsonify({"message": "Bid evaluated successfully!", "winner": {
        "id": winner.id,
        "bidder": winner.bidder,
        "price": winner.price,
        "completion_time": winner.completion_time
    }}), 200

# Temporal event management to auto-close tasks
def close_expired_tasks():
    with app.app_context():
        now = datetime.utcnow()
        expired_tasks = Task.query.filter(Task.deadline < now).all()
        for task in expired_tasks:
            db.session.delete(task)
        db.session.commit()
        print(f"Closed {len(expired_tasks)} expired tasks.")

# Scheduler setup
scheduler = BackgroundScheduler()
scheduler.add_job(func=close_expired_tasks, trigger="interval", minutes=1)
scheduler.start()

# Shutdown scheduler on app exit
@app.teardown_appcontext
def shutdown_scheduler(exception=None):
    scheduler.shutdown()

# Route for GUI interface
@app.route('/')
def home():
    return render_template('index.html')

# Ensure templates folder exists
if not os.path.exists('templates'):
    os.makedirs('templates')

# Create a simple HTML file for the GUI
html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bidding System</title>
</head>
<body>
    <h1>Welcome to the Bidding System</h1>
    <form id="createTaskForm">
        <h2>Create a Task</h2>
        <label for="title">Title:</label>
        <input type="text" id="title" name="title" required><br><br>
        <label for="description">Description:</label>
        <textarea id="description" name="description" required></textarea><br><br>
        <label for="deadline">Deadline (YYYY-MM-DD HH:MM:SS):</label>
        <input type="text" id="deadline" name="deadline" required><br><br>
        <label for="criteria">Criteria (lowest price / fastest completion):</label>
        <input type="text" id="criteria" name="criteria" required><br><br>
        <button type="submit">Create Task</button>
    </form>

    <script>
        document.getElementById('createTaskForm').addEventListener('submit', async (event) => {
            event.preventDefault();

            const title = document.getElementById('title').value;
            const description = document.getElementById('description').value;
            const deadline = document.getElementById('deadline').value;
            const criteria = document.getElementById('criteria').value;

            const response = await fetch('/tasks', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ title, description, deadline, criteria })
            });

            const result = await response.json();
            alert(result.message);
        });
    </script>
</body>
</html>"""

with open('templates/index.html', 'w') as file:
    file.write(html_content)

if __name__ == '__main__':
    app.run(debug=True)
