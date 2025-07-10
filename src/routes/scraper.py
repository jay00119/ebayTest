from flask import Blueprint, jsonify, request
import requests
from bs4 import BeautifulSoup
import time
import re
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from collections import Counter
import logging
import deepl

scraper_bp = Blueprint('scraper', __name__)

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TitleAnalyzer:
    def __init__(self):
        try:
            # 使用提供的DeepL API密钥
            self.deepl_client = deepl.Translator("55f08e38-e61d-4259-be1f-df716be00456:fx")
            logger.info("DeepL客户端初始化成功")
        except Exception as e:
            logger.error(f"DeepL客户端初始化失败: {str(e)}")
            self.deepl_client = None
        
        # 不需要翻译的词汇（品牌名、技术术语等）
        self.skip_translation = {
            # 品牌名
            'philips', 'hue', 'xiaomi', 'govee', 'nanoleaf', 'lifx', 'tp-link', 'kasa',
            'osram', 'ikea', 'amazon', 'alexa', 'google', 'apple', 'homekit',
            # 技术术语
            'led', 'rgb', 'rgbw', 'wifi', 'bluetooth', 'zigbee', 'usb', 'app',
            'ios', 'android', 'wlan', 'smart', 'home', 'dimmbar', 'dimmer',
            # 规格术语
            'e27', 'e14', 'gu10', 'mr16', 'g9', 'g4', 'cct', 'lumen', 'watt',
            'volt', 'ip65', 'ip44', 'ip20', 'ac', 'dc', 'uvp', 'ovp',
            # 常见英文词汇
            'set', 'kit', 'pack', 'bundle', 'new', 'original', 'genuine',
            'white', 'black', 'color', 'colour', 'warm', 'cool', 'bright'
        }
    
    def tokenize_titles(self, titles):
        """对标题进行分词处理"""
        try:
            all_words = []
            
            for title in titles:
                # 转换为小写
                title_lower = title.lower()
                
                # 使用正则表达式提取单词（包括数字和字母的组合）
                words = re.findall(r'\b[a-zA-Z0-9]+\b', title_lower)
                
                # 过滤掉太短的词和常见的停用词
                stop_words = {
                    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
                    'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
                    'will', 'would', 'could', 'should', 'may', 'might', 'can', 'must', 'shall',
                    'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they',
                    'my', 'your', 'his', 'her', 'its', 'our', 'their', 'me', 'him', 'her', 'us', 'them',
                    'not', 'no', 'yes', 'all', 'any', 'some', 'many', 'much', 'more', 'most', 'other',
                    'from', 'up', 'out', 'down', 'off', 'over', 'under', 'again', 'further', 'then', 'once'
                }
                
                filtered_words = [word for word in words if len(word) > 2 and word not in stop_words]
                all_words.extend(filtered_words)
            
            return all_words
        except Exception as e:
            logger.error(f"分词处理失败: {str(e)}")
            return []
    
    def get_top_keywords(self, words, top_n=50):
        """获取出现频率最高的关键词"""
        try:
            word_counts = Counter(words)
            return word_counts.most_common(top_n)
        except Exception as e:
            logger.error(f"获取关键词失败: {str(e)}")
            return []
    
    def batch_translate_keywords(self, keywords):
        """使用批量翻译优化性能和准确性"""
        try:
            translated_keywords = []
            
            # 分离需要翻译和不需要翻译的词汇
            need_translation = []
            skip_translation = []
            
            for keyword, count in keywords:
                if keyword.lower() in self.skip_translation or keyword.isdigit():
                    # 不需要翻译的词汇
                    skip_translation.append({
                        'original': keyword,
                        'count': count,
                        'english': keyword.upper() if keyword.lower() in ['led', 'rgb', 'rgbw', 'wifi', 'usb'] else keyword,
                        'chinese': self.get_chinese_mapping(keyword.lower())
                    })
                else:
                    need_translation.append((keyword, count))
            
            # 批量翻译需要翻译的词汇
            if need_translation and self.deepl_client:
                # 将关键词组合成批量翻译的文本
                keywords_to_translate = [kw[0] for kw in need_translation]
                
                try:
                    # 批量翻译到英文
                    en_translations = self.batch_translate_text(keywords_to_translate, "EN-US")
                    
                    # 批量翻译到中文
                    zh_translations = self.batch_translate_text(keywords_to_translate, "ZH")
                    
                    # 组合结果
                    for i, (keyword, count) in enumerate(need_translation):
                        translated_keywords.append({
                            'original': keyword,
                            'count': count,
                            'english': en_translations[i] if i < len(en_translations) else keyword,
                            'chinese': zh_translations[i] if i < len(zh_translations) else keyword
                        })
                        
                except Exception as e:
                    logger.error(f"批量翻译失败: {str(e)}")
                    # 如果批量翻译失败，回退到原始词汇
                    for keyword, count in need_translation:
                        translated_keywords.append({
                            'original': keyword,
                            'count': count,
                            'english': keyword,
                            'chinese': keyword
                        })
            else:
                # 如果没有DeepL客户端，直接使用原始词汇
                for keyword, count in need_translation:
                    translated_keywords.append({
                        'original': keyword,
                        'count': count,
                        'english': keyword,
                        'chinese': keyword
                    })
            
            # 合并结果
            all_translated = skip_translation + translated_keywords
            
            # 按出现频率排序
            all_translated.sort(key=lambda x: x['count'], reverse=True)
            
            return all_translated
            
        except Exception as e:
            logger.error(f"关键词翻译处理失败: {str(e)}")
            # 返回基本的关键词列表，不包含翻译
            return [{
                'original': keyword,
                'count': count,
                'english': keyword,
                'chinese': keyword
            } for keyword, count in keywords]
    
    def batch_translate_text(self, keywords, target_lang):
        """批量翻译文本"""
        try:
            if not self.deepl_client:
                logger.warning("DeepL客户端未初始化，跳过翻译")
                return keywords
                
            # 将关键词用换行符连接，便于批量翻译
            text_to_translate = '\n'.join(keywords)
            
            # 调用DeepL API进行批量翻译
            result = self.deepl_client.translate_text(text_to_translate, target_lang=target_lang)
            
            # 分割翻译结果
            translations = result.text.split('\n')
            
            # 确保翻译结果数量与输入一致
            while len(translations) < len(keywords):
                translations.append(keywords[len(translations)])
            
            return translations[:len(keywords)]
            
        except Exception as e:
            logger.error(f"批量翻译到{target_lang}失败: {str(e)}")
            return keywords
    
    def get_chinese_mapping(self, keyword):
        """获取常见技术术语的中文映射"""
        try:
            chinese_mapping = {
                'led': 'LED灯',
                'rgb': 'RGB彩色',
                'rgbw': 'RGBW彩色',
                'wifi': 'WiFi无线',
                'bluetooth': '蓝牙',
                'smart': '智能',
                'home': '家居',
                'dimmbar': '可调光',
                'dimmer': '调光器',
                'philips': '飞利浦',
                'hue': '飞利浦Hue',
                'xiaomi': '小米',
                'govee': 'Govee',
                'nanoleaf': 'Nanoleaf',
                'lifx': 'LIFX',
                'osram': '欧司朗',
                'ikea': '宜家',
                'amazon': '亚马逊',
                'alexa': 'Alexa',
                'google': '谷歌',
                'apple': '苹果',
                'homekit': 'HomeKit',
                'e27': 'E27螺口',
                'e14': 'E14螺口',
                'gu10': 'GU10插脚',
                'mr16': 'MR16射灯',
                'watt': '瓦特',
                'lumen': '流明',
                'warm': '暖光',
                'cool': '冷光',
                'white': '白色',
                'black': '黑色',
                'color': '彩色',
                'set': '套装',
                'kit': '套件',
                'pack': '包装',
                'new': '新品',
                'original': '原装'
            }
            
            return chinese_mapping.get(keyword, keyword)
        except Exception as e:
            logger.error(f"获取中文映射失败: {str(e)}")
            return keyword
    
    def analyze_titles(self, titles):
        """完整的标题分析流程"""
        try:
            if not titles:
                return {
                    'total_titles': 0,
                    'total_words': 0,
                    'unique_words': 0,
                    'top_keywords': []
                }
            
            logger.info(f"开始分析{len(titles)}个标题")
            
            # 分词
            words = self.tokenize_titles(titles)
            
            # 获取高频关键词
            top_keywords = self.get_top_keywords(words, 50)
            
            logger.info(f"找到{len(top_keywords)}个高频关键词，开始批量翻译")
            
            # 批量翻译关键词
            translated_keywords = self.batch_translate_keywords(top_keywords)
            
            logger.info(f"翻译完成，返回{len(translated_keywords)}个关键词")
            
            return {
                'total_titles': len(titles),
                'total_words': len(words),
                'unique_words': len(set(words)),
                'top_keywords': translated_keywords
            }
            
        except Exception as e:
            logger.error(f"标题分析失败: {str(e)}")
            return {
                'total_titles': len(titles) if titles else 0,
                'total_words': 0,
                'unique_words': 0,
                'top_keywords': [],
                'error': str(e)
            }

class EbayScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0'
        })
        
    def extract_titles_from_page(self, html_content):
        """从页面HTML中提取商品标题"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            titles = []
            
            # 选择器策略列表，按优先级排序
            selectors = [
                # 主要选择器：h3标签中带有textual-display bsig__title__text类的元素
                {'selector': 'h3', 'class_filter': lambda x: x and ('textual-display' in x and 'bsig__title__text' in x), 'name': 'primary'},
                
                # 备用选择器1：h3标签中带有s-item__title类的元素
                {'selector': 'h3', 'class_filter': lambda x: x and 's-item__title' in x, 'name': 'backup1'},
                
                # 备用选择器2：span标签中role="heading"的元素
                {'selector': 'span', 'attrs': {'role': 'heading'}, 'name': 'backup2'},
                
                # 备用选择器3：h3标签中包含item title相关类的元素
                {'selector': 'h3', 'class_filter': lambda x: x and ('item' in x.lower() and 'title' in x.lower()), 'name': 'backup3'},
                
                # 备用选择器4：a标签指向商品详情页（/itm/）
                {'selector': 'a', 'href_filter': lambda x: x and '/itm/' in x, 'name': 'backup4'},
                
                # 备用选择器5：通用标题选择器
                {'selector': 'h3', 'class_filter': lambda x: x and any(keyword in x.lower() for keyword in ['title', 'name', 'product']), 'name': 'backup5'}
            ]
            
            for selector_config in selectors:
                try:
                    if 'class_filter' in selector_config:
                        elements = soup.find_all(selector_config['selector'], class_=selector_config['class_filter'])
                    elif 'attrs' in selector_config:
                        elements = soup.find_all(selector_config['selector'], attrs=selector_config['attrs'])
                    elif 'href_filter' in selector_config:
                        elements = soup.find_all(selector_config['selector'], href=selector_config['href_filter'])
                    else:
                        continue
                    
                    found_count = 0
                    for element in elements:
                        title = element.get_text(strip=True)
                        if self.is_valid_title(title) and title not in titles:
                            titles.append(title)
                            found_count += 1
                    
                    logger.info(f"选择器 {selector_config['name']} 找到 {found_count} 个有效标题")
                    
                    # 如果找到足够多的标题，就停止尝试其他选择器
                    if len(titles) >= 20:
                        break
                        
                except Exception as e:
                    logger.warning(f"选择器 {selector_config['name']} 执行失败: {str(e)}")
                    continue
            
            return titles
            
        except Exception as e:
            logger.error(f"提取标题失败: {str(e)}")
            return []
    
    def is_valid_title(self, title):
        """验证标题是否有效"""
        try:
            if not title:
                return False
            
            # 长度检查
            if len(title) <= 5 or len(title) >= 300:
                return False
            
            # 过滤掉一些明显不是商品标题的内容
            invalid_patterns = [
                r'^Shop by category$',
                r'^Daily Deals$',
                r'^Brand Outlet$',
                r'^Help & Contact$',
                r'^Sell$',
                r'^Watchlist$',
                r'^My eBay$',
                r'^Notification$',
                r'^Cart$',
                r'^Sign in$',
                r'^Register$',
                r'^Advanced$',
                r'^Search$',
                r'^Categories$',
                r'^Motors$',
                r'^Fashion$',
                r'^Electronics$',
                r'^Collectibles$',
                r'^Home & Garden$',
                r'^Sporting Goods$',
                r'^Toys & Hobbies$',
                r'^Business & Industrial$',
                r'^Music$',
                r'^Deals & Savings$',
                r'^\d+$',  # 纯数字
                r'^[^\w\s]+$',  # 只包含特殊字符
                r'^(See all|View all|More)$',
                r'^(Previous|Next|Page \d+)$',
                r'^(Sort|Filter|Refine)$',
                r'^(Buy It Now|Auction|Best Offer)$',
                r'^(Free shipping|Fast \'N Free)$',
                r'^(Condition|Price|Time|Distance)$',
                r'^(New|Used|Refurbished|For parts)$',
            ]
            
            for pattern in invalid_patterns:
                if re.match(pattern, title, re.IGNORECASE):
                    return False
            
            # 检查是否包含常见的商品标题特征
            # 如果标题太短且不包含这些特征，可能不是商品标题
            if len(title) < 15:
                product_indicators = [
                    r'\b(new|used|vintage|original|genuine|authentic|brand)\b',
                    r'\b(for|with|in|on|by|from)\b',
                    r'\b(size|color|model|type|style)\b',
                    r'\b(set|kit|pack|bundle|lot)\b',
                    r'\d+',  # 包含数字
                    r'[A-Z]{2,}',  # 包含大写字母（可能是品牌名）
                ]
                
                has_indicator = any(re.search(pattern, title, re.IGNORECASE) for pattern in product_indicators)
                if not has_indicator:
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"标题验证失败: {str(e)}")
            return False
    
    def get_next_page_url(self, current_url, page_num):
        """生成下一页的URL"""
        try:
            parsed_url = urlparse(current_url)
            query_params = parse_qs(parsed_url.query)
            
            # 设置页码参数
            query_params['_pgn'] = [str(page_num)]
            
            # 重新构建URL
            new_query = urlencode(query_params, doseq=True)
            new_url = urlunparse((
                parsed_url.scheme,
                parsed_url.netloc,
                parsed_url.path,
                parsed_url.params,
                new_query,
                parsed_url.fragment
            ))
            
            return new_url
        except Exception as e:
            logger.error(f"生成下一页URL失败: {str(e)}")
            return None
    
    def scrape_page_with_retry(self, url, max_retries=3):
        """带重试机制的页面抓取"""
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                
                # 检查是否被重定向到错误页面
                if 'error' in response.url.lower() or 'blocked' in response.url.lower():
                    raise requests.RequestException("可能被反爬虫机制阻断")
                
                return response.text
                
            except requests.RequestException as e:
                logger.warning(f"第{attempt + 1}次尝试抓取失败: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # 指数退避
                else:
                    raise e
    
    def scrape_titles(self, start_url, max_pages=4):
        """抓取商品标题"""
        try:
            all_titles = []
            successful_pages = 0
            
            for page_num in range(1, max_pages + 1):
                try:
                    if page_num == 1:
                        url = start_url
                    else:
                        url = self.get_next_page_url(start_url, page_num)
                        if not url:
                            logger.error(f"无法生成第{page_num}页的URL")
                            continue
                    
                    logger.info(f"正在抓取第{page_num}页: {url}")
                    
                    html_content = self.scrape_page_with_retry(url)
                    titles = self.extract_titles_from_page(html_content)
                    
                    if titles:
                        logger.info(f"第{page_num}页找到{len(titles)}个标题")
                        all_titles.extend(titles)
                        successful_pages += 1
                    else:
                        logger.warning(f"第{page_num}页未找到任何标题")
                    
                    # 添加延迟以避免被反爬虫机制阻断
                    if page_num < max_pages:
                        time.sleep(2)
                        
                except requests.RequestException as e:
                    logger.error(f"抓取第{page_num}页时发生网络错误: {str(e)}")
                    continue
                except Exception as e:
                    logger.error(f"处理第{page_num}页时发生未知错误: {str(e)}")
                    continue
            
            # 去重
            unique_titles = list(dict.fromkeys(all_titles))
            logger.info(f"总共抓取到{len(unique_titles)}个唯一标题，成功抓取{successful_pages}页")
            
            return unique_titles, successful_pages
            
        except Exception as e:
            logger.error(f"抓取过程失败: {str(e)}")
            return [], 0

@scraper_bp.route('/scrape', methods=['POST'])
def scrape_ebay():
    """eBay商品标题抓取API端点"""
    try:
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({'error': '请提供eBay页面URL'}), 400
        
        url = data['url'].strip()
        
        # 验证URL是否为eBay域名
        parsed_url = urlparse(url)
        if not parsed_url.netloc or 'ebay' not in parsed_url.netloc.lower():
            return jsonify({'error': '请提供有效的eBay页面URL'}), 400
        
        # 创建爬虫实例并开始抓取
        scraper = EbayScraper()
        titles, successful_pages = scraper.scrape_titles(url)
        
        if not titles:
            return jsonify({
                'error': '未能抓取到任何商品标题，请检查URL是否正确或稍后重试',
                'successful_pages': successful_pages
            }), 404
        
        return jsonify({
            'success': True,
            'titles': titles,
            'count': len(titles),
            'successful_pages': successful_pages,
            'message': f'成功抓取{successful_pages}页，共获得{len(titles)}个商品标题'
        })
        
    except Exception as e:
        logger.error(f"抓取过程中发生错误: {str(e)}")
        return jsonify({'error': f'抓取失败: {str(e)}'}), 500

@scraper_bp.route('/analyze', methods=['POST'])
def analyze_titles():
    """分析标题并提供分词统计和翻译"""
    try:
        data = request.get_json()
        if not data or 'titles' not in data:
            return jsonify({'error': '请提供标题列表'}), 400
        
        titles = data['titles']
        
        if not titles:
            return jsonify({'error': '标题列表不能为空'}), 400
        
        logger.info(f"开始分析{len(titles)}个标题")
        
        # 创建分析器实例并进行分析
        analyzer = TitleAnalyzer()
        analysis_result = analyzer.analyze_titles(titles)
        
        logger.info(f"分析完成，找到{len(analysis_result.get('top_keywords', []))}个关键词")
        
        return jsonify({
            'success': True,
            'analysis': analysis_result
        })
        
    except Exception as e:
        logger.error(f"分析过程中发生错误: {str(e)}")
        return jsonify({'error': f'分析失败: {str(e)}'}), 500

