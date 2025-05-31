import re
import os
import requests
import datetime
from dotenv import load_dotenv

from flask import Flask, request, jsonify, render_template
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

load_dotenv()
app = Flask(__name__)

# ENV variable setup
API_URL = os.getenv('API_URL', '')
API_TOKEN = os.getenv('API_TOKEN', '')
MODEL = os.getenv('MODEL', '')

# Mongo setup
app.config["MONGO_URI"] = os.getenv('MONGO_URI', '')
if not app.config["MONGO_URI"]:
    raise ValueError("MONGO_URI environment variable not set")
mongo = PyMongo(app)
client = MongoClient(app.config["MONGO_URI"], server_api=ServerApi('1'))

# ========== AI model support functions ========== #
# API setup
HEADERS = {"Authorization": "Bearer {}".format(API_TOKEN)}

def getSuggestionFromLLM(goal, start_date, target_date, requirement):
    print("Fetching answer from Hugging Face router API")
    payload = {
        "messages": [
            {
                "role": "user",
                "content": (
                    f"Generate list of tasks based on provided goal, start date (dd/mm/yyyy) target date (dd/mm/yyyy) and requirement description"
                    f"For each task, generate the task name and expected completion date. Make sure to distribute tasks reasonably from start date to achieve goal before target date"
                    f"Format your response as follows:\n"
                    f"**TASK 1:** [Task name here]?\n"
                    f"**DATE:** [Expected completion date here]\n"
                    f"**TASK 2:** [Task name here]?\n"
                    f"**DATE:** [Expected completion date here]\n"
                    f"Number of tasks is not limited to 2, add more task based on your analysis for the given information."
                    f"Ensure text is properly formatted. It needs to start with a task name, then the completion date."
                    f"Follow this pattern for all tasks. "
                    f"Here is the information for you to generate: \nGoal: {goal} \nStart date: {start_date} \nTarget date: {target_date} \nRequirement: {requirement}"
                )
            }
        ],
        "model": MODEL,
        "max_tokens": 500,
        "temperature": 0.7,
        "top_p": 0.9
    }

    response = requests.post(API_URL, headers=HEADERS, json=payload)
    if response.status_code == 200:
        result = response.json()["choices"][0]["message"]["content"]
        print("=== [RECEIVED RESULT] ===")
        print(result)
        return result
    else:
        raise Exception(f"API request failed: {response.status_code} - {response.text}")

def process_answer(answer_text):
    task_list = []
    # Updated regex to match bolded format with numbered questions
    pattern = re.compile(
        r'\*\*TASK \d+:\*\*\s+(.+?)\s+'
        r'\*\*DATE:\*\*\s+(.+?)\s+',
        re.DOTALL
    )
    matches = pattern.findall(answer_text)

    for match in matches:
        task_name = match[0].strip()
        date = match[1].strip()

        task_data = {
            "name": task_name.replace("*", ""),
            "date": date.replace("*", "")
        }
        task_list.append(task_data)
    
    message = answer_text.replace("*", "")
    return message, task_list

# ========== AI API routes ========== #
# Get quiz
@app.route('/ai/getTaskSuggestion', methods=['GET'])
def get_task_suggestion():
    print("=== [RECEIVED REQUEST] ===")
    goal = request.args.get('goal')
    target_date = request.args.get('end')
    requirement = request.args.get('requirement')
    # start_date = request.args.get('start')
    start_date = datetime.datetime.today().strftime('%d/%m/%Y')

    if (not goal) or (not start_date) or (not target_date) or (not requirement):
        return jsonify({'error': 'Missing parameters'}), 400
    try:
        answer = getSuggestionFromLLM(goal, start_date, target_date, requirement)
        processed_message, processed_answer = process_answer(answer)
        
        print("=== [PROCESSED RESULT] ===")
        print(processed_message)
        print(processed_answer)
        if (not processed_message) or (not processed_answer):
            return jsonify({'error': 'Failed to parse quiz data', 'raw_response': answer}), 500
        
        return jsonify({'message': processed_message, 'task': processed_answer}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
@app.route('/ai/saveGeneratedTask', methods=['POST'])
def save_task_suggestion():
    try:
        goal = {
            "user_id": ObjectId(request.json['user_id']),
            "name": request.json["goal_name"],
            "date": request.json["goal_date"],
            "finish": False,
        }
        goal_result = mongo.db.goals.insert_one(goal)
        goal_id = goal_result.inserted_id

        task_list = request.json["task_list"]
        for task in task_list:
            task["goal_id"] = goal_id
            task["user_id"] = ObjectId(task["user_id"])
            task["finish"] = False
        mongo.db.tasks.insert_many(task_list)

        return jsonify({"message": "Data added successfully"}), 201
    except Exception as e:
        return jsonify({"error": f"Failed to add new data: {str(e)}"}), 400
    
# ========== User routes ========== #
@app.route("/user/register", methods=["POST"])
def register_user():
    
    try:
        user = {
            "name": request.json["name"],
            "email": request.json["email"],
            "password": request.json["password"]
        }

        check_result = list(mongo.db.users.find({"email": user["email"]}))
        if (len(check_result)!=0):
            return jsonify({"error": "Email already existed"}), 400
        
        result = mongo.db.users.insert_one(user)
        user["_id"] = str(result.inserted_id)
        return jsonify({"message": "User added successfully", "user": user}), 201
    except Exception as e:
        return jsonify({"error": f"Failed to add new user: {str(e)}"}), 400

@app.route("/user/login", methods=["POST"])
def login_user():
    try:
        result = list(mongo.db.users.find({
            "email": request.json["email"] ,
            "password": request.json["password"]
        }))
        if (len(result)==0):
            return jsonify({"error": "Email or password is incorrect"}), 400

        user = result[0]
        user["_id"] = str(user["_id"])
        return jsonify({"message": "Login successfully", "user": user}), 201
    except Exception as e:
        return jsonify({"error": f"Failed to login: {str(e)}"}), 400

@app.route("/user/delete/<id>", methods=["DELETE"])
def delete_user(id):
    try:
        mongo.db.users.delete_one({"_id": ObjectId(id)})
        mongo.db.tasks.delete_many({"user_id": ObjectId(id)})
        mongo.db.goals.delete_many({"user_id": ObjectId(id)})

        return jsonify({"message": "User deleted successfully"}), 200
    except Exception as e:
        return jsonify({"error": f"Failed to login: {str(e)}"}), 400

# ========== Task routes ========== #
@app.route("/task", methods=["POST"])
def add_task():
    try:
        task = {
            "user_id": ObjectId(request.json["user_id"]),
            "goal_id": ObjectId(request.json["goal_id"]),
            "name": request.json["name"],
            "date": request.json["date"],
            "finish": False,
        }
        result = mongo.db.tasks.insert_one(task)

        task["_id"] = str(result.inserted_id)
        return jsonify({"message": "Task added successfully", "task": task}), 201
    except Exception as e:
        return jsonify({"error": f"Failed to add new task: {str(e)}"}), 400

@app.route("/task", methods=["GET"])
def get_all_tasks():
    try:
        if (request.args['goal_id'] != ""):
            goal_id = ObjectId(request.args['goal_id'])
            tasks = list(mongo.db.tasks.find({
                "user_id": ObjectId(request.args['user_id']),
                "goal_id": ObjectId(goal_id),
                "finish": request.args['finish'] == "1"
            }))
        else:
            tasks = list(mongo.db.tasks.find({
                "user_id": ObjectId(request.args['user_id']),
                "finish": request.args['finish'] == "1"
            }))
        
        for task in tasks:
            task["_id"] = str(task["_id"])
            task["user_id"] = str(task["user_id"])
            task["goal_id"] = str(task["goal_id"])
        return jsonify({"message": "Get task data successfully", "tasks": tasks}), 201
    except Exception as e:
        return jsonify({"error": f"Failed to get task data: {str(e)}"}), 400

@app.route("/task/<id>", methods=["PUT"])
def update_task(id):
    try:
        task_data = {
            "goal_id": ObjectId(request.json["goal_id"]),
            "name": request.json["name"],
            "date": request.json["date"]
        }
        result = mongo.db.tasks.update_one(
            {"_id": ObjectId(id)},
            {"$set": task_data}
        )
        
        if result.modified_count:
            task_data["_id"] = id
            task_data["goal_id"] = str(task_data["goal_id"])
            return jsonify({"message": "Task updated successfully", "task": task_data}), 200
        return jsonify({"error": "Task not found"}), 404
    except Exception as e:
        return jsonify({"error": f"Failed to update task: {str(e)}"}), 400
    
@app.route("/task/<id>", methods=["DELETE"])
def delete_task(id):
    try:
        result = mongo.db.tasks.delete_one({"_id": ObjectId(id)})
        if result.deleted_count:
            return jsonify({"message": "Task deleted successfully"}), 200
        
        return jsonify({"error": "Task not found"}), 404
    except Exception as e:
        return jsonify({"error": f"Failed to delete task: {str(e)}"}), 400
    
@app.route("/task/finish/<id>", methods=["PUT"])
def mark_finish_task(id):
    try:
        task_data = {
            "finish": True
        }
        result = mongo.db.tasks.update_one(
            {"_id": ObjectId(id)},
            {"$set": task_data}
        )
        
        if result.modified_count:
            return jsonify({"message": "Task updated successfully"}), 200
        return jsonify({"error": "Task not found"}), 404
    except Exception as e:
        return jsonify({"error": f"Failed to update task: {str(e)}"}), 400
    
# ========== Goal routes ========== #
@app.route("/goal", methods=["POST"])
def add_goal():
    try:
        goal = {
            "user_id": ObjectId(request.json['user_id']),
            "name": request.json["name"],
            "date": request.json["date"],
            "finish": False,
        }
        result = mongo.db.goals.insert_one(goal)

        goal["_id"] = str(result.inserted_id)
        return jsonify({"message": "Goal added successfully", "goal": goal}), 201
    except Exception as e:
        return jsonify({"error": f"Failed to add new goal: {str(e)}"}), 400

@app.route("/goal", methods=["GET"])
def get_all_goals():
    try:
        goals = list(mongo.db.goals.find({
            "user_id": ObjectId(request.args['user_id']),
            "finish": request.args['finish'] == "1"
        }))

        for goal in goals:
            goal["_id"] = str(goal["_id"])
            goal["user_id"] = str(goal["user_id"])
        return jsonify({"message": "Get goal data successfully", "goals": goals}), 201
    except Exception as e:
        return jsonify({"error": f"Failed to get goal data: {str(e)}"}), 400

@app.route("/goal/<id>", methods=["PUT"])
def update_goal(id):
    try:
        goal_data = {
            "name": request.json["name"],
            "date": request.json["date"],
        }
        result = mongo.db.goals.update_one(
            {"_id": ObjectId(id)},
            {"$set": goal_data}
        )
        
        if result.modified_count:
            return jsonify({"message": "Goal updated successfully"}), 200
        return jsonify({"error": "Goal not found"}), 404
    except Exception as e:
        return jsonify({"error": f"Failed to update goal: {str(e)}"}), 400

@app.route("/goal/finish/<id>", methods=["PUT"])
def mark_finish_goal(id):
    try:
        goal_data = {
            "finish": True
        }
        result = mongo.db.goals.update_one(
            {"_id": ObjectId(id)},
            {"$set": goal_data}
        )
        
        if result.modified_count:
            return jsonify({"message": "Goal updated successfully"}), 200
        return jsonify({"error": "Goal not found"}), 404
    except Exception as e:
        return jsonify({"error": f"Failed to update goal: {str(e)}"}), 400
    
@app.route("/goal/<id>", methods=["DELETE"])
def delete_goal(id):
    try:
        result = mongo.db.goals.delete_one({"_id": ObjectId(id)})
        if result.deleted_count:
            return jsonify({"message": "Goal deleted successfully"}), 200
        
        return jsonify({"error": "Goal not found"}), 404
    except Exception as e:
        return jsonify({"error": f"Failed to delete goal: {str(e)}"}), 400
    
# Launch server
if __name__ == '__main__':
    port_num = 5000
    print(f"App running on port {port_num}")
    app.run(port=port_num, host="0.0.0.0")