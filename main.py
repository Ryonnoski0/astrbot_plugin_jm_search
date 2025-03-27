from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from PIL import Image
import jmcomic, yaml, os, time
import requests
import json
import astrbot.api.message_components as Comp


def all2PDF(input_folder, pdfpath, pdfname, event=None):
    start_time = time.time()
    paht = input_folder
    zimulu = []  # 子目录（里面为image）
    image = []  # 子目录图集
    sources = []  # pdf格式的图

    if event:
        chain = [Comp.At(qq=event.get_sender_id()), Comp.Plain("开始整理图片文件...")]
        yield event.chain_result(chain)

    with os.scandir(paht) as entries:
        for entry in entries:
            if entry.is_dir():
                zimulu.append(int(entry.name))
    # 对数字进行排序
    zimulu.sort()

    for i in zimulu:
        with os.scandir(paht + "/" + str(i)) as entries:
            for entry in entries:
                if entry.is_dir():
                    print("这一级不应该有自录")
                if entry.is_file():
                    image.append(paht + "/" + str(i) + "/" + entry.name)

    if event:
        chain = [
            Comp.At(qq=event.get_sender_id()),
            Comp.Plain(f"已找到 {len(image)} 张图片，开始转换为PDF..."),
        ]
        yield event.chain_result(chain)

    if "jpg" in image[0]:
        output = Image.open(image[0])
        image.pop(0)

    total_images = len(image)
    for idx, file in enumerate(image):
        if "jpg" in file:
            img_file = Image.open(file)
            if img_file.mode == "RGB":
                img_file = img_file.convert("RGB")
            sources.append(img_file)

            # 每处理20%的图片报告一次进度
            if event and idx % max(1, total_images // 5) == 0:
                progress_percent = (idx / total_images) * 100
                chain = [
                    Comp.At(qq=event.get_sender_id()),
                    Comp.Plain(
                        f"PDF转换进度: {progress_percent:.1f}% ({idx}/{total_images})"
                    ),
                ]
                yield event.chain_result(chain)

    if event:
        chain = [Comp.At(qq=event.get_sender_id()), Comp.Plain("正在保存PDF文件...")]
        yield event.chain_result(chain)

    pdf_file_path = pdfpath + "/" + pdfname
    if pdf_file_path.endswith(".pdf") == False:
        pdf_file_path = pdf_file_path + ".pdf"
    output.save(pdf_file_path, "pdf", save_all=True, append_images=sources)
    end_time = time.time()
    run_time = end_time - start_time
    print("运行时间：%3.2f 秒" % run_time)

    if event:
        chain = [
            Comp.At(qq=event.get_sender_id()),
            Comp.Plain(f"PDF生成完成！用时 {run_time:.2f} 秒"),
        ]
        yield event.chain_result(chain)

    return pdf_file_path


@register("jmSearch", "Ryonnoski", "禁漫搜索", "1.0.0")
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    # 注册指令的装饰器
    @filter.command("jm")
    async def jm(self, event: AstrMessageEvent, id: int = None):
        """使用/jm id 可以搜索禁漫"""  # 这是 handler 的描述，将会被解析方便用户了解插件内容。建议填写。

        # 检查是否提供了ID
        if id is None:
            chain = [
                Comp.At(qq=event.get_sender_id()),
                Comp.Plain("请提供禁漫ID，例如：/jm 12345"),
            ]
            yield event.chain_result(chain)
            return

        chain = [
            Comp.At(qq=event.get_sender_id()),
            Comp.Plain(f"开始下载ID为 {id} 的禁漫，请稍候..."),
        ]
        yield event.chain_result(chain)

        # 获取网络连接状态
        try:
            response = requests.get("https://httpbin.org/anything")
            data = json.loads(response.text)
            print("Request headers sent:", data["headers"])
            print("Origin IP:", data["origin"])
        except Exception as e:
            chain = [
                Comp.At(qq=event.get_sender_id()),
                Comp.Plain(f"网络连接检查失败: {str(e)}"),
            ]
            yield event.chain_result(chain)
            return

        user_name = event.get_sender_name()
        message_str = event.message_str
        message_chain = event.get_messages()
        logger.info(message_chain)

        # 加载配置
        config = os.path.join(
            os.getcwd(), "data", "plugins", "astrbot_plugin_jm_search", "config.yml"
        )

        try:
            loadConfig = jmcomic.JmOption.from_file(config)

            # 我们将使用一个计数器来跟踪进度，因为JmOption的回调不能直接使用yield
            download_start_time = time.time()
            last_report_time = 0

            # 在下载前发送通知
            chain = [
                Comp.At(qq=event.get_sender_id()),
                Comp.Plain(f"开始下载ID: {id}..."),
            ]
            yield event.chain_result(chain)

            # 下载漫画
            jmcomic.download_album(id, loadConfig)

            # 下载完成通知
            download_time = time.time() - download_start_time
            chain = [
                Comp.At(qq=event.get_sender_id()),
                Comp.Plain(f"下载完成！用时 {download_time:.2f} 秒。开始生成PDF..."),
            ]
            yield event.chain_result(chain)

            # 加载配置路径
            with open(config, "r", encoding="utf8") as f:
                data = yaml.load(f, Loader=yaml.FullLoader)
                path = data["dir_rule"]["base_dir"]

            # 查找刚下载的漫画目录并转换为PDF
            latest_entry = None
            with os.scandir(path) as entries:
                for entry in entries:
                    if entry.is_dir():
                        # 检查是否已经有对应的PDF
                        if os.path.exists(os.path.join(path, entry.name + ".pdf")):
                            latest_entry = entry
                            continue
                        else:
                            latest_entry = entry
                            # 使用生成器函数转换PDF并报告进度
                            pdf_generator = all2PDF(
                                path + "/" + entry.name, path, entry.name, event
                            )
                            for result in pdf_generator:
                                yield result

            if latest_entry:
                # 转换完成，发送文件
                pdf_path = os.path.abspath(path + "/" + latest_entry.name + ".pdf")
                chain = [
                    Comp.At(qq=event.get_sender_id()),
                    Comp.Plain("来看这个文件："),
                    Comp.File(
                        file=pdf_path,
                        name=latest_entry.name + ".pdf",
                    ),
                    Comp.Plain("这是一个pdf。"),
                ]
                yield event.chain_result(chain)
            else:
                chain = [
                    Comp.At(qq=event.get_sender_id()),
                    Comp.Plain("未找到需要转换的漫画目录。"),
                ]
                yield event.chain_result(chain)

        except Exception as e:
            chain = [
                Comp.At(qq=event.get_sender_id()),
                Comp.Plain(f"处理过程中出错: {str(e)}"),
            ]
            yield event.chain_result(chain)

    @filter.command("jmhelp")
    async def jmhelp(self, event: AstrMessageEvent):
        """使用/jmhelp 可以查看帮助"""  # 这是 handler 的描述，将会被解析方便用户了解插件内容。建议填写。
        yield event.plain_result("输入/jm id 可以搜索禁漫")
