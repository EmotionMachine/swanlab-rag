import gradio as gr
from chat_logic_loacl import Chatbot

# --- 1. 初始化后端 ---
print("正在创建 Chatbot 实例...")
chatbot_instance = Chatbot()
print("Chatbot 实例创建成功。")


# --- 2. 定义 Gradio 的核心函数 ---
def add_user_message(message, history):
    if not message.strip():
        return gr.update(value=""), history
    history.append([message, None])
    return gr.update(value=""), history


# 函数B: 耗时的AI处理 (接收更新后的history，填充AI回复)
def predict(history, last_question_id, debug_log_state):
    user_message = history[-1][0]

    response_generator = chatbot_instance.stream_chat(user_message, history[:-1], previous_debug_log=debug_log_state)

    q_id = None
    debug_log = debug_log_state
    for answer_chunk, q_id_chunk, debug_chunk in response_generator:
        history[-1][1] = answer_chunk
        if q_id_chunk:
            q_id = q_id_chunk
        debug_log = debug_chunk
        yield history, q_id, debug_log


def handle_feedback(feedback_choice, last_id):
    if last_id is None:
        gr.Warning("当前没有可以反馈的问答。")
        return
    feedback_result = chatbot_instance.add_feedback(last_id, feedback_choice.lower())
    gr.Info(feedback_result)


# --- 3. 构建 Gradio UI ---
custom_css = """
/* 全局字体和全屏布局 */
body, .gradio-container { font-family: "Inter", "Helvetica Neue", "Helvetica", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "微软雅黑", "Arial", sans-serif !important; }
.gradio-container { max-width: 100% !important; padding: 0 !important; margin: 0 !important; }
html, body { height: 100%; overflow: hidden; }
#main_block { height: 100vh; display: flex; flex-direction: column; }

/* ✅ 使用 Flexbox 布局左侧聊天栏 */
#left_column { display: flex; flex-direction: column; height: 100%; }
#chatbot { flex-grow: 1; overflow-y: auto; } /* 让聊天框占据所有可用垂直空间并可以滚动 */
#input_area { flex-shrink: 0; padding: 10px; border-top: 1px solid #E5E7EB; background-color: white;} /* 让输入区域固定在底部，不收缩 */

/* 调试日志框也填满高度 */
#right_column { height: 100%; display: flex; flex-direction: column; }
#debug_output > .wrap { flex-grow: 1; } /* 让Textbox的包装器填满空间 */
#debug_output > .wrap > textarea { height: 100% !important; } /* 让textarea本身也填满 */

"""

with gr.Blocks(theme=gr.themes.Soft(), css=custom_css, fill_height=True, elem_id="main_block") as demo:
    last_question_id = gr.State(None)
    debug_log_state = gr.State("")

    gr.HTML("""
        <div style="display: flex; align-items: center; justify-content: center; flex-direction: column; position: relative;">
            <div style="display: flex; align-items: center;">
                <img src="swanlab.svg" alt="SwanLab Logo" style="height: 50px; margin-right: 10px;">
                <h1 style="margin: 0;">SwanLab Copilot</h1>
            </div>
            <div style="font-size: 12px; color: gray; margin-top: 5px;">
                beta 1
            </div>
        </div>
        """)

    with gr.Row(equal_height=False, elem_classes="flex-grow: 1; overflow: hidden;"):
        # --- 左侧：聊天界面 ---
        with gr.Column(scale=1, elem_id="left_column"):
            chatbot = gr.Chatbot(
                elem_id="chatbot",  # 用于CSS定位
                value=[(None, "你好！我是 SwanLab 文档的智能问答助手，有什么可以帮您？")],
                show_copy_button=True,
                bubble_full_width=False,
            )

            #  将输入框和按钮打包到底部固定区域
            with gr.Column(elem_id="input_area"):
                msg_textbox = gr.Textbox(
                    placeholder="输入消息(Enter发送, Shift+Enter换行)",
                    container=False,
                    scale=4,
                    show_label=False,
                )
                with gr.Row():
                    submit_btn = gr.Button("发送", variant="primary", scale=1)
                    clear_btn = gr.ClearButton(
                        # 清空按钮现在也需要清空调试日志的显示
                        components=[msg_textbox, chatbot, last_question_id, debug_log_state],
                        value="清空所有状态"
                    )
                    correct_btn = gr.Button("✅ 正确")
                    incorrect_btn = gr.Button("❌ 错误")

        # --- 右侧：调试日志界面 ---
        with gr.Column(scale=1, elem_id="right_column"):
            debug_output = gr.Textbox(
                label="后端实时日志",
                interactive=False,
                autoscroll=True,
                max_lines=40,
                elem_id="debug_output"
            )

    # --- 4. 绑定事件 ---
    # 统一定义一个事件处理流程
    process_event = (
        msg_textbox.submit(
            fn=add_user_message,
            inputs=[msg_textbox, chatbot],
            outputs=[msg_textbox, chatbot],
            queue=False
        ).then(
            fn=predict,
            inputs=[chatbot, last_question_id, debug_log_state],
            outputs=[chatbot, last_question_id, debug_output]
        )
    )

    submit_btn.click(
        fn=add_user_message,
        inputs=[msg_textbox, chatbot],
        outputs=[msg_textbox, chatbot],
        queue=False
    ).then(
        fn=predict,
        inputs=[chatbot, last_question_id, debug_log_state],
        outputs=[chatbot, last_question_id, debug_output]
    )

    correct_btn.click(fn=handle_feedback, inputs=[gr.Textbox("correct", visible=False), last_question_id], outputs=None)
    incorrect_btn.click(fn=handle_feedback, inputs=[gr.Textbox("incorrect", visible=False), last_question_id],
                        outputs=None)

# --- 5. 启动应用 ---
if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)