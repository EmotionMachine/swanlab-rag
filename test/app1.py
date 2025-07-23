import gradio as gr
from chat_logic_loacl import Chatbot

# --- 1. Initialize Backend Logic ---
# This assumes chat_logic_loacl.py is in the same directory.
print("正在创建 Chatbot 实例...")
try:
    chatbot_instance = Chatbot()
    print("Chatbot 实例创建成功。")
except Exception as e:
    print(f"创建 Chatbot 实例时发生错误: {e}")
    # Exit if the backend can't be initialized
    exit()

# --- 2. Define Gradio Core Functions ---

def add_user_message(message, history):
    """Adds a user's message to the chat history."""
    if not message.strip():
        # Prevent sending empty messages
        return gr.update(value=""), history
    history.append([message, None])
    return gr.update(value=""), history


def predict(history, last_question_id):
    """
    Handles the core chat logic by streaming the bot's response.
    This version is simplified to ignore the debug log output.
    """
    user_message = history[-1][0]

    # Call the backend, ignoring the debug log it produces (the third item in the tuple)
    response_generator = chatbot_instance.stream_chat(user_message, history[:-1])

    q_id = last_question_id
    for answer_chunk, q_id_chunk, _ in response_generator:
        history[-1][1] = answer_chunk
        if q_id_chunk:
            q_id = q_id_chunk
        yield history, q_id


def handle_feedback(feedback_choice, last_id):
    """Sends user feedback (correct/incorrect) to the backend."""
    if last_id is None:
        gr.Warning("当前没有可以反馈的问答。")
        return
    feedback_result = chatbot_instance.add_feedback(last_id, feedback_choice.lower())
    gr.Info(feedback_result)


# --- 3. Build the Gradio UI ---

# Simplified CSS for a single-column layout
custom_css = """
/* Apply a modern font and ensure the app uses the full viewport height */
body, .gradio-container {
    font-family: "Inter", "Helvetica Neue", "Helvetica", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "微软雅黑", "Arial", sans-serif !important;
    height: 100vh;
}

/* Main block flex container to structure the layout */
#main_block {
    height: 100%;
    display: flex;
    flex-direction: column;
}

/* Make the chatbot area grow to fill available space and scroll independently */
#chatbot_wrapper {
    flex-grow: 1;
    overflow-y: auto;
    min-height: 0; /* Important for flex-grow in a column layout */
}

/* Style for the input area at the bottom */
#input_area {
    flex-shrink: 0; /* Prevent the input area from shrinking */
    padding: 12px;
    border-top: 1px solid #E5E7EB;
    background-color: white;
}
"""

with gr.Blocks(theme=gr.themes.Soft(), css=custom_css, fill_height=True, elem_id="main_block") as demo:
    # State to store the ID of the last question for feedback
    last_question_id = gr.State(None)

    gr.Markdown("# 🤖 AI 文档助手")

    # The main chat interface
    with gr.Column(elem_id="chatbot_wrapper"):
        chatbot = gr.Chatbot(
            elem_id="chatbot",
            value=[(None, "你好！我是 SwanLab 文档的智能问答助手，有什么可以帮您？")],
            show_copy_button=True,
            bubble_full_width=False,
            height="100%"
        )

    # The input controls at the bottom of the page
    with gr.Column(elem_id="input_area"):
        msg_textbox = gr.Textbox(
            placeholder="输入您的问题 (按 Enter 发送, Shift+Enter 换行)",
            container=False,
            scale=4,
            show_label=False,
        )
        with gr.Row():
            submit_btn = gr.Button("🚀 发送", variant="primary", scale=1)
            clear_btn = gr.ClearButton(
                components=[msg_textbox, chatbot, last_question_id],
                value="🗑️ 清空对话"
            )

    # The feedback buttons, which are now more prominent
    with gr.Row(elem_id="feedback_area"):
        gr.Markdown("您对回答满意吗？", scale=2)
        correct_btn = gr.Button("✅ 满意")
        incorrect_btn = gr.Button("❌ 不满意")


    # --- 4. Bind UI Events to Functions ---

    # Define the event flow for submitting a message
    submit_event = (
        msg_textbox.submit(
            fn=add_user_message,
            inputs=[msg_textbox, chatbot],
            outputs=[msg_textbox, chatbot],
            queue=False  # Run immediately
        ).then(
            fn=predict,
            inputs=[chatbot, last_question_id],
            outputs=[chatbot, last_question_id]
        )
    )

    submit_btn.click(
        fn=add_user_message,
        inputs=[msg_textbox, chatbot],
        outputs=[msg_textbox, chatbot],
        queue=False
    ).then(
        fn=predict,
        inputs=[chatbot, last_question_id],
        outputs=[chatbot, last_question_id]
    )

    # Bind feedback buttons
    correct_btn.click(
        fn=handle_feedback,
        inputs=[gr.Textbox("correct", visible=False), last_question_id],
        outputs=None
    )
    incorrect_btn.click(
        fn=handle_feedback,
        inputs=[gr.Textbox("incorrect", visible=False), last_question_id],
        outputs=None
    )

# --- 5. Launch the Application ---
if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)