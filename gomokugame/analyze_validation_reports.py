import os
import json
from collections import defaultdict
from datetime import datetime
import glob
import argparse

def analyze_validation_reports(reports_dir='validation_reports'):
    """
    分析validation_reports目录下的所有对战报告
    
    Args:
        reports_dir (str): 包含对战报告的目录路径
        
    Returns:
        dict: 包含统计数据的字典
    """
    print(f"正在分析目录: {reports_dir}")
    
    # 检查目录是否存在
    if not os.path.exists(reports_dir):
        print(f"错误: 目录 {reports_dir} 不存在")
        return None
    
    # 获取所有JSON报告文件
    report_files = glob.glob(os.path.join(reports_dir, "*.json"))
    
    print(f"目录中共找到 {len(report_files)} 个JSON文件:")
    for file_path in report_files:
        size = os.path.getsize(file_path)
        print(f"  {os.path.basename(file_path)} ({size} 字节)")
    
    # 过滤掉太小的文件（可能是空文件或损坏文件）
    valid_reports = []
    for file_path in report_files:
        if os.path.getsize(file_path) > 1000:  # 大于1KB的文件才认为是有效的
            valid_reports.append(file_path)
    
    print(f"\n其中大于1KB的有效文件有 {len(valid_reports)} 个:")
    for file_path in valid_reports:
        size = os.path.getsize(file_path)
        print(f"  {os.path.basename(file_path)} ({size} 字节)")
    
    print(f"\n准备分析最新的8个有效报告...")
    
    # 初始化统计数据
    stats = {
        'total_reports': len(valid_reports),
        'version_stats': defaultdict(lambda: {'wins': 0, 'losses': 0, 'total_games': 0, 'win_rates': []}),
        'trend_counts': {'improving': 0, 'declining': 0, 'stable': 0},
        'latest_reports': [],
    }
    
    # 处理每个报告文件
    for i, file_path in enumerate(valid_reports):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 添加到最新报告列表（按时间排序，只保留最新的8个）
            timestamp_str = data.get('timestamp', '1900-01-01T00:00:00')
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00')) if 'T' in timestamp_str else datetime.min
            
            stats['latest_reports'].append({
                'file': os.path.basename(file_path),
                'timestamp': timestamp,
                'data': data
            })
        except Exception as e:
            print(f"处理文件 {file_path} 时出错: {e}")
    
    # 按时间戳排序并保留最新的8个报告
    stats['latest_reports'].sort(key=lambda x: x['timestamp'], reverse=True)
    latest_8_reports = stats['latest_reports'][:8]
    
    print(f"\n实际分析的 {len(latest_8_reports)} 个报告文件:")
    for i, report in enumerate(latest_8_reports):
        file_name = report['file']
        timestamp = report['timestamp'].strftime('%Y-%m-%d %H:%M:%S') if report['timestamp'] != datetime.min else 'Unknown'
        print(f"  {i+1}. {file_name} (时间: {timestamp})")
    
    print(f"\n详细分析结果:")
    for i, report in enumerate(latest_8_reports):
        file_name = report['file']
        timestamp = report['timestamp'].strftime('%Y-%m-%d %H:%M:%S') if report['timestamp'] != datetime.min else 'Unknown'
        data = report['data']
        
        print(f"\n报告 {i+1}: {file_name} (时间: {timestamp})")
        
        # 显示版本统计
        versions_tested = data.get('versions_tested', [])
        version_stats = data.get('version_stats', {})
        
        print("  版本统计:")
        for version_num in versions_tested:
            v_key = str(version_num)
            if v_key in version_stats:
                stats_data = version_stats[v_key]
                wins = stats_data['wins']
                total = stats_data['total_games']
                win_rate = stats_data['win_rate'] if 'win_rate' in stats_data else (wins / total if total > 0 else 0)
                
                print(f"    版本 {version_num}: {wins}/{total} 胜率: {win_rate:.2%}")
                
                # 更新总统计
                stats['version_stats'][f'v{version_num}']['wins'] += wins
                stats['version_stats'][f'v{version_num}']['losses'] += stats_data['losses']
                stats['version_stats'][f'v{version_num}']['total_games'] += total
                stats['version_stats'][f'v{version_num}']['win_rates'].append(win_rate)
        
        # 显示学习趋势
        learning_analysis = data.get('learning_analysis', {})
        trend = learning_analysis.get('trend', 'unknown')
        stats['trend_counts'][trend] += 1
        
        first_win_rate = learning_analysis.get('first_version_win_rate', 0)
        last_win_rate = learning_analysis.get('last_version_win_rate', 0)
        
        print(f"  学习趋势: {trend} (初始胜率: {first_win_rate:.2%}, 最终胜率: {last_win_rate:.2%})")
    
    # 输出汇总统计
    print("\n" + "="*50)
    print("汇总统计")
    print("="*50)
    
    print(f"\n总共分析报告数: {len(latest_8_reports)}")
    
    print("\n各版本整体表现:")
    for version, data in sorted(stats['version_stats'].items()):
        total_wins = data['wins']
        total_games = data['total_games']
        avg_win_rate = sum(data['win_rates']) / len(data['win_rates']) if data['win_rates'] else 0
        max_win_rate = max(data['win_rates']) if data['win_rates'] else 0
        min_win_rate = min(data['win_rates']) if data['win_rates'] else 0
        
        print(f"  {version}:")
        print(f"    总战绩: {total_wins}胜/{total_games-total_wins}负 ({total_games}局)")
        print(f"    平均胜率: {avg_win_rate:.2%}")
        print(f"    最高胜率: {max_win_rate:.2%}")
        print(f"    最低胜率: {min_win_rate:.2%}")
    
    print("\n学习趋势分布:")
    for trend, count in stats['trend_counts'].items():
        print(f"  {trend}: {count} 次 ({count/len(latest_8_reports)*100:.1f}%)")
    
    return stats

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='分析validation_reports目录下的对战报告')
    parser.add_argument('subdir', nargs='?', default='validation_reports', 
                        help='要分析的子目录名称 (默认: validation_reports)')
    
    args = parser.parse_args()
    
    # 如果提供了子目录名称，则构建完整路径
    if args.subdir == 'validation_reports':
        reports_dir = 'validation_reports'
    else:
        reports_dir = os.path.join('validation_reports', args.subdir)
    
    # 运行分析
    analysis_result = analyze_validation_reports(reports_dir)