import gradio as gr
from chat_logic_deploy import Chatbot
import uuid
from flask import Flask, request, jsonify

# 初始化后端
print("正在创建 Chatbot 实例...")
chatbot_instance = Chatbot()
print("Chatbot 实例创建成功。")


# 定义核心函数
def add_user_message(message, history, user_id):
    if not message.strip():
        return gr.update(value=""), history

    # 如果user_id为空，生成一个新的UUID并创建用户
    if not user_id:
        import uuid
        new_user_id = str(uuid.uuid4())
        # 创建用户记录
        chatbot_instance.create_user(new_user_id)
        # 添加用户消息并返回新的user_id
        history.append([message, None])
        return gr.update(value=""), history, new_user_id

    # 如果user_id已存在，正常处理消息
    history.append([message, None])
    return gr.update(value=""), history, user_id


def predict(history, last_question_id, user_id):
    user_message = history[-1][0]
    response_generator = chatbot_instance.stream_chat(user_message, history[:-1], user_id)

    q_id = None
    for item in response_generator:
        if not isinstance(item, tuple) or len(item) != 2:
            print(f"错误：生成器返回了无效格式的数据: {item}")  # 调试信息
            continue
        answer_chunk, q_id_chunk = item
        history[-1][1] = answer_chunk
        if q_id_chunk:
            q_id = q_id_chunk
        yield history, q_id


def handle_feedback(feedback_choice, last_id):
    if last_id is None:
        gr.Warning("当前没有可以反馈的问答。")
        return
    feedback_result = chatbot_instance.add_feedback(last_id, feedback_choice.lower())
    # gr.Info(feedback_result)


def get_example_questions():
    return [
        "SwanLab是什么？",
        "如何安装SwanLab？",
        "SwanLab支持哪些实验跟踪功能？",
        "如何使用SwanLab进行超参数优化？",
        "SwanLab如何与PyTorch集成？"
    ]


# 自定义CSS样式
custom_css = """
/* 全局样式 */
body, .gradio-container { 
    font-family: "Inter", "Helvetica Neue", "Helvetica", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "微软雅黑", "Arial", sans-serif !important; 
}
.gradio-container { 
    max-width: 1200px !important; 
    margin: 0 auto !important; 
    padding: 20px !important;
}
.main-header {
    text-align: center;
    margin-bottom: 30px;
}
.main-header h1 {
    color: #1a73e8;
    font-size: 2.5rem;
    margin-bottom: 10px;
}
.main-header p {
    color: #5f6368;
    font-size: 1.1rem;
}
.chat-container {
    display: flex;
    flex-direction: column;
    height: 70vh;
    border-radius: 12px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    overflow: hidden;
}
.chatbot {
    flex-grow: 1;
    overflow-y: auto;
    background-color: #f8f9fa;
    padding: 15px;
}
.input-area {
    padding: 15px;
    background-color: white;
    border-top: 1px solid #e0e0e0;
}
.feedback-area {
    margin-top: 10px;
    display: flex;
    justify-content: center;
    gap: 10px;
}
.example-area {
    margin-top: 20px;
    padding: 15px;
    background-color: #f1f3f4;
    border-radius: 8px;
}
.example-area h3 {
    margin-top: 0;
    color: #202124;
}
.example-btn {
    margin: 5px;
    border-radius: 20px;
}
.footer {
    text-align: center;
    margin-top: 30px;
    color: #5f6368;
    font-size: 0.9rem;
}

/* 修复聊天气泡样式 - 关键部分 */
.chatbot .message {
    padding: 0 !important;
    margin: 10px 0 !important;
    border-radius: 0 !important;
    background: none !important;
    box-shadow: none !important;
    border: none !important;
}

.chatbot .message-row {
    margin: 0 !important;
}

.chatbot .message .user {
    background-color: #e8f0fe !important;
    border-radius: 18px 18px 4px 18px !important;
    padding: 10px 15px !important;
    margin: 0 0 0 auto !important;
    max-width: 80% !important;
    box-shadow: 0 1px 2px rgba(0,0,0,0.1) !important;
}

.chatbot .message .bot {
    background-color: white !important;
    border-radius: 18px 18px 18px 4px !important;
    padding: 10px 15px !important;
    margin: 0 auto 0 0 !important;
    max-width: 80% !important;
    box-shadow: 0 1px 2px rgba(0,0,0,0.1) !important;
}

/* 移除可能导致小白条的伪元素 */
.chatbot .message::before,
.chatbot .message::after {
    display: none !important;
}

/* 确保聊天气泡内部没有多余元素 */
.chatbot .message .md {
    padding: 0 !important;
    margin: 0 !important;
}

/* 移除可能的边框和阴影 */
.chatbot .message .user,
.chatbot .message .bot {
    border: none !important;
}

/* 反馈按钮样式优化 */
.feedback-area {
    margin-top: 15px;
    display: flex;
    justify-content: center;
    gap: 15px;
}

.feedback-area button {
    border-radius: 20px;
    padding: 8px 15px;
    font-size: 0.9rem;
    transition: all 0.2s ease;
}

.feedback-area button:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 8px rgba(0,0,0,0.1);
}

/* 在每条消息后添加反馈按钮区域 */
.message-feedback {
    display: flex;
    justify-content: flex-end;
    margin-top: 5px;
    margin-right: 20%;
    gap: 10px;
}

.message-feedback button {
    border: none;
    background: none;
    cursor: pointer;
    font-size: 1.2rem;
    opacity: 0.7;
    transition: opacity 0.2s;
}

.message-feedback button:hover {
    opacity: 1;
}
"""

# 构建Gradio UI
with gr.Blocks(theme=gr.themes.Soft(), css=custom_css, title="SwanLab AI文档助手") as demo:
    # 添加用户ID状态 - 简单创建，不添加额外参数
    user_id = gr.State("")
    last_question_id = gr.State(None)

    # 页面头部
    with gr.Column(elem_classes="main-header"):
        gr.Markdown("# SwanLab AI文档助手")
        gr.Markdown("### 基于SwanLab官方文档的智能问答系统")

    # 聊天主区域
    with gr.Column(elem_classes="chat-container"):
        chatbot = gr.Chatbot(
            elem_classes="chatbot",
            value=[(None, "👋 你好！我是SwanLab文档的智能问答助手。有什么可以帮助您的吗？")],
            show_copy_button=True,
            bubble_full_width=False,
            height=500,
            # 添加自定义布局，在每条消息后添加反馈按钮
            layout="panel"
        )

        # 输入区域
        with gr.Column(elem_classes="input-area"):
            # 反馈按钮区域（移到输入区域上方，更靠近回答）
            with gr.Row(elem_classes="feedback-area"):
                correct_btn = gr.Button("👍 回答有帮助", variant="secondary")
                incorrect_btn = gr.Button("👎 回答无帮助", variant="secondary")
                feedback_btn = gr.Button("反馈", link="https://rcnpx636fedp.feishu.cn/share/base/form/shrcnjjKzm8U5PQ3vik9pvLJVYb")
                clear_btn = gr.Button("清空对话", variant="secondary")

            with gr.Row():
                msg_textbox = gr.Textbox(
                    placeholder="输入您的问题，按Enter发送...",
                    container=False,
                    scale=4,
                    show_label=False
                )
                submit_btn = gr.Button("发送", variant="primary", scale=1)

    # 示例问题区域
    with gr.Column(elem_classes="example-area"):
        gr.Markdown("### 💡 常见问题示例")
        examples = gr.Examples(
            examples=get_example_questions(),
            inputs=[msg_textbox],
            label="点击以下问题快速开始",
            examples_per_page=5
        )

    # 页脚
    with gr.Column(elem_classes="footer"):
        gr.Markdown("© 2025 SwanLab AI文档助手 | 基于SwanLab官方文档构建")

    # 添加 Gradio JavaScript API 初始化
    gradio_js = """
    <script>
        // 扩展 Gradio 配置以支持状态操作
        window.addEventListener('load', function() {
            if (window.gradio_config) {
                // 添加设置状态的方法
                window.gradio_config.set_state = function(componentId, value) {
                    const component = window.gradio_config.components.find(c => c.id === componentId);
                    if (component) {
                        component.value = value;
                        // 更新对应的 textarea
                        const textarea = document.querySelector(`#${componentId} textarea`);
                        if (textarea) {
                            textarea.value = value;
                        }
                    }
                };

                // 添加获取状态的方法
                window.gradio_config.get_state = function(componentId) {
                    const component = window.gradio_config.components.find(c => c.id === componentId);
                    return component ? component.value : null;
                };
            }
        });
    </script>
    """
    gr.HTML(gradio_js)

    # 添加自定义HTML和JavaScript用于用户管理
    custom_html = """
    <script>
        function generateUUID() {
            return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
                const r = Math.random() * 16 | 0;
                const v = c == 'x' ? r : (r & 0x3 | 0x8);
                return v.toString(16);
            });
        }

        // 页面加载时生成用户ID并创建用户记录
        document.addEventListener("DOMContentLoaded", function() {
            console.log(Swanlab AI文档助手已加载)

        // 页面关闭时更新用户退出时间
        window.addEventListener("beforeunload", function() {
            // 尝试获取用户ID
            let userId = null;

            // 使用 Gradio 的 JavaScript API 获取状态值
            if (window.gradio_config && window.gradio_config.components) {
                const stateComponents = window.gradio_config.components.filter(
                    component => component.type === 'state'
                );

                if (stateComponents.length >= 1) {
                    const userIdComponent = stateComponents[0];
                    userId = window.gradio_config.get_state(userIdComponent.id);
                }
            }

            if (userId) {
                navigator.sendBeacon('/update_user_exit', JSON.stringify({
                    user_id: userId
                }));
            }
        });
    </script>
    """
    gr.HTML(custom_html)

    # 修改事件绑定，添加用户ID参数
    msg_textbox.submit(
        fn=add_user_message,
        inputs=[msg_textbox, chatbot, user_id],
        outputs=[msg_textbox, chatbot, user_id],
        queue=False
    ).then(
        fn=predict,
        inputs=[chatbot, last_question_id, user_id],
        outputs=[chatbot, last_question_id]
    )

    submit_btn.click(
        fn=add_user_message,
        inputs=[msg_textbox, chatbot, user_id],
        outputs=[msg_textbox, chatbot, user_id],
        queue=False
    ).then(
        fn=predict,
        inputs=[chatbot, last_question_id, user_id],
        outputs=[chatbot, last_question_id]
    )

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

    clear_btn.click(
        fn=lambda: [None, []],
        outputs=[last_question_id, chatbot]
    )

# 添加Flask路由处理用户管理 - 增强调试版
app = demo.app


@app.route('/create_user', methods=['POST'])
def create_user():
    print("=== CREATE USER ROUTE CALLED ===")
    data = request.json
    print("Request data:", data)
    user_id = data.get('user_id')
    if user_id:
        result = chatbot_instance.create_user(user_id)
        print(f"User creation result: {result}")
        return jsonify({"status": "success", "user_id": user_id})
    print("Missing user_id in request")
    return jsonify({"status": "error", "message": "Missing user_id"}), 400


@app.route('/update_user_exit', methods=['POST'])
def update_user_exit():
    print("=== UPDATE USER EXIT ROUTE CALLED ===")
    data = request.json
    print("Request data:", data)
    user_id = data.get('user_id')
    if user_id:
        chatbot_instance.update_user_exit(user_id)
        return jsonify({"status": "success"})
    print("Missing user_id in request")
    return jsonify({"status": "error", "message": "Missing user_id"}), 400


# 启动应用
if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860, #选择端口
        share=True,
        ssl_keyfile="私钥路径",  #私钥路径
        ssl_certfile="公钥路径"  #公钥路径
    )