from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from PIL import Image
import jmcomic, yaml, os, time
import requests
import json
import astrbot.api.message_components as Comp
import hashlib  # 导入 hashlib 模块用于计算 MD5


# 不加密的使用方式（与原来相同）
def all2PDF(input_folder, pdfpath, pdfname, event=None, password=None):
    start_time = time.time()
    path = input_folder
    zimulu = []  # 子目录（里面为image）
    image = []  # 子目录图集
    sources = []  # pdf格式的图

    # if event:
    #     chain = [Comp.At(qq=event.get_sender_id()), Comp.Plain("开始整理图片文件...")]
    #     yield event.chain_result(chain)

    with os.scandir(path) as entries:
        for entry in entries:
            if entry.is_dir():
                zimulu.append(int(entry.name))
    # 对数字进行排序
    zimulu.sort()

    for i in zimulu:
        with os.scandir(path + "/" + str(i)) as entries:
            for entry in entries:
                if entry.is_dir():
                    print("这一级不应该有子目录")
                if entry.is_file():
                    image.append(path + "/" + str(i) + "/" + entry.name)

    # if event:
    #     chain = [
    #         Comp.At(qq=event.get_sender_id()),
    #         Comp.Plain(f"已找到 {len(image)} 张图片，开始转换为PDF..."),
    #     ]
    #     yield event.chain_result(chain)

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

            # # 每处理50%的图片报告一次进度
            # if (
            #     event and idx > 0 and idx % max(1, total_images // 2) == 0
            # ):  # 添加 idx > 0 条件
            #     progress_percent = (idx / total_images) * 100
            #     chain = [
            #         Comp.At(qq=event.get_sender_id()),
            #         Comp.Plain(
            #             f"PDF转换进度: {progress_percent:.1f}% ({idx}/{total_images})"
            #         ),
            #     ]
            #     yield event.chain_result(chain)

    if event:
        chain = [
            Comp.At(qq=event.get_sender_id()),
            Comp.Plain("正在保存PDF并尝试加密..."),
        ]
        yield event.chain_result(chain)

    # 创建临时PDF文件路径
    temp_pdf_path = pdfpath + "/temp_" + pdfname
    if not temp_pdf_path.endswith(".pdf"):
        temp_pdf_path = temp_pdf_path + ".pdf"

    # 最终PDF文件路径
    pdf_file_path = pdfpath + "/" + pdfname
    if not pdf_file_path.endswith(".pdf"):
        pdf_file_path = pdf_file_path + ".pdf"

    # 先保存为未加密的PDF
    output.save(temp_pdf_path, "pdf", save_all=True, append_images=sources)

    # 如果提供了密码，则添加密码保护
    if password:
        # if event:
        #     chain = [
        #         Comp.At(qq=event.get_sender_id()),
        #         Comp.Plain("正在为PDF添加密码保护..."),
        #     ]
        #     yield event.chain_result(chain)

        try:
            from PyPDF2 import PdfReader, PdfWriter

            reader = PdfReader(temp_pdf_path)
            writer = PdfWriter()

            # 复制所有页面到新的PDF
            for page in reader.pages:
                writer.add_page(page)

            # 添加密码保护
            writer.encrypt(password)

            # 保存加密后的PDF
            with open(pdf_file_path, "wb") as f:
                writer.write(f)

            # 删除临时文件
            os.remove(temp_pdf_path)

        except ImportError:
            if event:
                chain = [
                    Comp.At(qq=event.get_sender_id()),
                    Comp.Plain(
                        "警告：未安装PyPDF2库，无法添加密码保护。请使用pip install PyPDF2安装。"
                    ),
                ]
                yield event.chain_result(chain)
            # 如果没有PyPDF2，就直接使用未加密的文件
            os.rename(temp_pdf_path, pdf_file_path)
    else:
        # 如果没有提供密码，直接重命名临时文件
        os.rename(temp_pdf_path, pdf_file_path)

    end_time = time.time()
    run_time = end_time - start_time
    print("运行时间：%3.2f 秒" % run_time)

    if event:
        protection_msg = "（已加密保护）" if password else ""
        chain = [
            Comp.At(qq=event.get_sender_id()),
            Comp.Plain(f"PDF生成完成！{protection_msg}用时 {run_time:.2f} 秒"),
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
            Comp.Plain(f"开始下载ID为 {id} 的禁漫 并尝试转为pdf，请稍候..."),
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
            # chain = [
            #     Comp.At(qq=event.get_sender_id()),
            #     Comp.Plain(f"开始下载ID: {id}..."),
            # ]
            # yield event.chain_result(chain)

            # 下载漫画
            album, _ = jmcomic.download_album(id, loadConfig)
            # print(benzi.file_name)
            # 下载完成通知
            # download_time = time.time() - download_start_time
            # chain = [
            #     Comp.At(qq=event.get_sender_id()),
            #     Comp.Plain(f"下载完成！用时 {download_time:.2f} 秒。开始生成PDF..."),
            # ]
            # yield event.chain_result(chain)

            # 加载配置路径
            with open(config, "r", encoding="utf8") as f:
                data = yaml.load(f, Loader=yaml.FullLoader)
                path = data["dir_rule"]["base_dir"]

            # 查找刚下载的漫画目录并转换为PDF
            pdf_filename = album.name + ".pdf"
            pdf_path = os.path.abspath(path + "/" + pdf_filename)
            pdf_file_path = "file://" + pdf_path
            # 首先检查是否已经存在对应的PDF文件
            if os.path.exists(pdf_path):
                print(f"PDF文件已存在，无需重新生成。{pdf_path}")
                # PDF已找到，准备发送文件
                chain = [
                    Comp.At(qq=event.get_sender_id()),
                    Comp.File(
                        file=pdf_file_path,
                        name=pdf_filename,
                    ),
                ]
                yield event.chain_result(chain)
            else:
                # 没找到PDF，寻找对应的目录来转换
                target_dir = None
                with os.scandir(path) as entries:
                    for entry in entries:
                        if entry.is_dir() and entry.name == album.name:
                            target_dir = entry
                            break

                if target_dir:
                    md5_hash = hashlib.md5(str(id).encode()).hexdigest()
                    # 找到了目录，开始转换
                    pdf_generator = all2PDF(
                        path + "/" + target_dir.name, path, album.name, event, md5_hash
                    )
                    for result in pdf_generator:
                        yield result

                    # 转换完成后，检查PDF是否成功生成
                    print(f"PDF文件路径: {pdf_path}")
                    if os.path.exists(pdf_path):
                        chain = [
                            Comp.At(qq=event.get_sender_id()),
                            Comp.File(
                                file=pdf_file_path,
                                name=pdf_filename,
                            ),
                        ]
                        yield event.chain_result(chain)
                    else:
                        chain = [
                            Comp.At(qq=event.get_sender_id()),
                            Comp.Plain("PDF转换似乎失败了，未找到生成的PDF文件。"),
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
