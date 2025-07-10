from flask import Blueprint, jsonify, request
import logging

test_bp = Blueprint('test', __name__)

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@test_bp.route('/test', methods=['GET', 'POST'])
def test_api():
    """简单的测试API端点"""
    try:
        logger.info("测试API被调用")
        
        if request.method == 'POST':
            data = request.get_json()
            logger.info(f"收到POST数据: {data}")
            return jsonify({
                'success': True,
                'message': 'POST请求成功',
                'received_data': data
            })
        else:
            return jsonify({
                'success': True,
                'message': 'GET请求成功',
                'method': 'GET'
            })
            
    except Exception as e:
        logger.error(f"测试API错误: {str(e)}", exc_info=True)
        return jsonify({'error': f'测试失败: {str(e)}'}), 500

@test_bp.route('/analyze-simple', methods=['POST'])
def analyze_simple():
    """简化的分析API端点，包含DeepL翻译"""
    try:
        logger.info("简化分析API被调用")
        
        data = request.get_json()
        if not data or 'titles' not in data:
            return jsonify({'error': '请提供标题列表'}), 400
        
        titles = data['titles']
        
        # 导入必要的模块
        from collections import Counter
        import re
        import deepl
        
        # 初始化DeepL客户端
        try:
            deepl_client = deepl.Translator("55f08e38-e61d-4259-be1f-df716be00456:fx")
            logger.info("DeepL客户端初始化成功")
        except Exception as e:
            logger.error(f"DeepL客户端初始化失败: {str(e)}")
            deepl_client = None
        
        # 简单的关键词分析
        all_words = []
        for title in titles:
            words = re.findall(r'\b[a-zA-Z0-9]+\b', title.lower())
            # 过滤停用词
            stop_words = {
                'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
                'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did'
            }
            filtered_words = [word for word in words if len(word) > 2 and word not in stop_words]
            all_words.extend(filtered_words)
        
        word_counts = Counter(all_words)
        top_keywords = word_counts.most_common(50)
        
        # 构建结果，包含翻译
        keywords_result = []
        total_count = sum(count for _, count in top_keywords)
        
        # 预定义的中文映射
        chinese_mapping = {
            'led': 'LED灯',
            'rgb': 'RGB彩色',
            'smart': '智能',
            'home': '家居',
            'philips': '飞利浦',
            'hue': '色调',
            'light': '灯光',
            'bulb': '灯泡',
            'strip': '灯带',
            'wifi': 'WiFi',
            'bluetooth': '蓝牙',
            'dimmer': '调光器',
            'white': '白色',
            'color': '彩色',
            'warm': '暖光',
            'cool': '冷光',
            'bright': '明亮',
            'set': '套装',
            'kit': '套件',
            'pack': '包装',
            'new': '新品',
            'original': '原装'
        }
        
        for i, (keyword, count) in enumerate(top_keywords, 1):
            percentage = round((count / total_count) * 100, 2) if total_count > 0 else 0
            
            # 英文翻译（标准化）
            english_word = keyword.upper() if keyword.lower() in ['led', 'rgb', 'wifi', 'usb'] else keyword
            
            # 中文翻译
            chinese_word = chinese_mapping.get(keyword.lower(), keyword)
            
            # 如果有DeepL客户端且不在预定义映射中，尝试翻译
            if deepl_client and keyword.lower() not in chinese_mapping:
                try:
                    result = deepl_client.translate_text(keyword, target_lang="ZH")
                    chinese_word = result.text
                except Exception as e:
                    logger.warning(f"翻译关键词 '{keyword}' 失败: {str(e)}")
                    # 保持原词
                    chinese_word = keyword
            
            keywords_result.append({
                'rank': i,
                'original': keyword,
                'count': count,
                'percentage': percentage,
                'english': english_word,
                'chinese': chinese_word
            })
        
        result = {
            'success': True,
            'analysis': {
                'total_titles': len(titles),
                'total_words': len(all_words),
                'unique_words': len(set(all_words)),
                'top_keywords': keywords_result
            }
        }
        
        logger.info(f"简化分析完成，返回{len(keywords_result)}个关键词")
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"简化分析API错误: {str(e)}", exc_info=True)
        return jsonify({'error': f'分析失败: {str(e)}'}), 500

