# Backend API for PlanEase - Android Application
Backend API source code for **PlanEase** project at [TUT888/PlanEase-AndroidApp](https://github.com/TUT888/PlanEase-AndroidApp)

## API endpoints
- AI-related endpoints:
    - **[GET] /ai/getTaskSuggestion**
    - **[POST] /ai/saveGeneratedTask**
- User-related endpoints:
    - **[POST] /user/register**
    - **[POST] /user/login**
    - **[DELETE] /user/delete/id**
- Task-related endpoints:
    - **[POST] /task**
    - **[GET] /task**:
    - **[PUT] /task/id**
    - **[DELETE] /task/id**
    - **[PUT] /task/finish/id**
- Goal-related endpoints:
    - **[POST] /goal**
    - **[GET] /goal**:
    - **[PUT] /goal/id**
    - **[DELETE] /goal/id**
    - **[PUT] /goal/finish/id**

## How to run
1. Clone this repo.
2. Create python virtual environment, activate it and installed required dependencies.
3. Setup Mongo Atlas and get the connection URI.
4. Create `.env` file with following information
    ```
    API_TOKEN=<Your generated token>
    API_URL=https://router.huggingface.co/nebius/v1/chat/completions
    MODEL=google/gemma-2-2b-it
    MONGO_URI=<PATH_TO_YOUR_MONGO_ATLAS>
    ```
5. Run the files
    ```
    python main_api.py
    ```
6. Use the IP address shown on your terminal for Android Application
    - Use IP on your local network (Ex: `http://192.168.0.1`)
    - **Avoid using loop back addresss** (Ex: `localhost` or `http://127.0.0.1`) because Android Virtual Devices can not access to this kind address on our computer

## Reference
Model and inference used in project
- LLM model: [google/gemma-2-2b-it](https://huggingface.co/google/gemma-2-2b-it)
- Nebius provider: [Nebius AI Studio Documentation](https://docs.nebius.com/studio/api/examples)

Other:
- About inference provider: [Inference Provider](https://huggingface.co/docs/inference-providers/en/index)
- Search model by inference provider: [Hugging Face - Inference Providers](https://huggingface.co/models?other=conversational&sort=likes)
