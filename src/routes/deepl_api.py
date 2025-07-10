from flask import Blueprint, jsonify, request
import logging
from collections import Counter
import re
import deepl

deepl_bp = Blueprint('deepl', __name__)

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@deepl_bp.route('/analyze-deepl', methods=['POST'])
def analyze_with_deepl():
    """使用DeepL翻译的分析API端点"""
    try:
        logger.info("DeepL分析API被调用")
        
        data = request.get_json()
        if not data or 'titles' not in data:
            return jsonify({'error': '请提供标题列表'}), 400
        
        titles = data['titles']
        
        # 初始化DeepL客户端
        try:
            deepl_client = deepl.Translator("55f08e38-e61d-4259-be1f-df716be00456:fx")
            logger.info("DeepL客户端初始化成功")
        except Exception as e:
            logger.error(f"DeepL客户端初始化失败: {str(e)}")
            return jsonify({'error': f'DeepL初始化失败: {str(e)}'}), 500
        
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
        top_keywords = word_counts.most_common(20)  # 减少到20个关键词以降低API调用量
        
        # 构建结果，使用DeepL翻译
        keywords_result = []
        total_count = sum(count for _, count in top_keywords)
        
        # 批量准备需要翻译的关键词
        keywords_to_translate = [keyword for keyword, _ in top_keywords]
        
        try:
            # 批量翻译到中文
            logger.info(f"开始翻译{len(keywords_to_translate)}个关键词")
            
            # 将关键词用换行符连接进行批量翻译
            text_to_translate = '\n'.join(keywords_to_translate)
            result = deepl_client.translate_text(text_to_translate, target_lang="ZH")
            chinese_translations = result.text.split('\n')
            
            # 确保翻译结果数量匹配
            while len(chinese_translations) < len(keywords_to_translate):
                chinese_translations.append(keywords_to_translate[len(chinese_translations)])
            
            logger.info("DeepL翻译完成")
            
        except Exception as e:
            logger.error(f"DeepL翻译失败: {str(e)}")
            # 如果翻译失败，使用原词
            chinese_translations = keywords_to_translate
        
        for i, (keyword, count) in enumerate(top_keywords):
            percentage = round((count / total_count) * 100, 2) if total_count > 0 else 0
            
            # 英文翻译（标准化）
            english_word = keyword.upper() if keyword.lower() in ['led', 'rgb', 'wifi', 'usb'] else keyword
            
            # 中文翻译
            chinese_word = chinese_translations[i] if i < len(chinese_translations) else keyword
            
            keywords_result.append({
                'rank': i + 1,
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
        
        logger.info(f"DeepL分析完成，返回{len(keywords_result)}个关键词")
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"DeepL分析API错误: {str(e)}", exc_info=True)
        return jsonify({'error': f'分析失败: {str(e)}'}), 500

