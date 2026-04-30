"""
Simple visualizations for bug prediction results.
Creates easy-to-understand charts without complex dependencies.
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import os


def create_risk_dashboard(df, repo_name, output_dir="ml/plots"):
    """
    Create a simple, easy-to-understand dashboard with 3 charts:
    1. Risk Tier Distribution (pie chart)
    2. Top 10 Riskiest Files (horizontal bar chart)
    3. Risk vs LOC scatter (shows which files are high-risk AND large)
    
    Args:
        df: DataFrame with risk predictions
        repo_name: Name of repository
        output_dir: Where to save the plot
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Create figure with 3 subplots
    fig = plt.figure(figsize=(16, 10))
    gs = fig.add_gridspec(2, 2, hspace=0.3, wspace=0.3)
    
    # Color scheme
    colors = {
        'CRITICAL': '#D32F2F',  # Red
        'HIGH': '#F57C00',      # Orange
        'MODERATE': '#FBC02D',  # Yellow
        'LOW': '#388E3C'        # Green
    }
    
    # ========== CHART 1: Risk Tier Distribution (Pie) ==========
    ax1 = fig.add_subplot(gs[0, 0])
    
    tier_counts = df['risk_tier'].value_counts()
    tier_order = ['CRITICAL', 'HIGH', 'MODERATE', 'LOW']
    tier_counts = tier_counts.reindex(tier_order, fill_value=0)
    
    wedges, texts, autotexts = ax1.pie(
        tier_counts.values,
        labels=[f"{tier}\n({count} files)" for tier, count in zip(tier_counts.index, tier_counts.values)],
        colors=[colors[tier] for tier in tier_counts.index],
        autopct='%1.1f%%',
        startangle=90,
        textprops={'fontsize': 11, 'weight': 'bold'}
    )
    
    ax1.set_title(f'Risk Distribution - {repo_name}\n({len(df)} files analyzed)', 
                  fontsize=14, weight='bold', pad=20)
    
    # ========== CHART 2: Top 10 Riskiest Files (Horizontal Bar) ==========
    ax2 = fig.add_subplot(gs[0, 1])
    
    top_10 = df.nlargest(10, 'risk')[['file', 'risk', 'risk_tier', 'loc']].copy()
    top_10['filename'] = top_10['file'].apply(lambda x: os.path.basename(str(x)))
    
    # Create bars
    y_pos = np.arange(len(top_10))
    bars = ax2.barh(y_pos, top_10['risk'].values, 
                    color=[colors[tier] for tier in top_10['risk_tier'].values],
                    edgecolor='black', linewidth=1.5)
    
    # Add LOC labels on bars
    for i, (risk, loc) in enumerate(zip(top_10['risk'].values, top_10['loc'].values)):
        ax2.text(risk - 0.05, i, f'{int(loc)} LOC', 
                va='center', ha='right', fontsize=9, weight='bold', color='white')
    
    ax2.set_yticks(y_pos)
    ax2.set_yticklabels(top_10['filename'].values, fontsize=10)
    ax2.set_xlabel('Risk Score', fontsize=12, weight='bold')
    ax2.set_title('Top 10 Riskiest Files', fontsize=14, weight='bold', pad=20)
    ax2.set_xlim(0, 1.0)
    ax2.grid(axis='x', alpha=0.3, linestyle='--')
    ax2.invert_yaxis()
    
    # ========== CHART 3: Risk vs LOC Scatter ==========
    ax3 = fig.add_subplot(gs[1, :])
    
    # Plot all files
    for tier in tier_order:
        tier_df = df[df['risk_tier'] == tier]
        ax3.scatter(tier_df['loc'], tier_df['risk'], 
                   c=colors[tier], label=tier, s=100, alpha=0.6, edgecolors='black')
    
    # Highlight top 5 with labels
    top_5 = df.nlargest(5, 'risk')
    for _, row in top_5.iterrows():
        filename = os.path.basename(str(row['file']))
        ax3.annotate(filename, 
                    xy=(row['loc'], row['risk']),
                    xytext=(10, 10), textcoords='offset points',
                    fontsize=9, weight='bold',
                    bbox=dict(boxstyle='round,pad=0.5', facecolor='yellow', alpha=0.7),
                    arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0'))
    
    ax3.set_xlabel('Lines of Code (LOC)', fontsize=12, weight='bold')
    ax3.set_ylabel('Risk Score', fontsize=12, weight='bold')
    ax3.set_title('Risk vs File Size (Larger files with high risk need more attention)', 
                  fontsize=14, weight='bold', pad=20)
    ax3.legend(loc='lower right', fontsize=11, framealpha=0.9)
    ax3.grid(alpha=0.3, linestyle='--')
    ax3.set_ylim(0, 1.05)
    
    # Add quadrant lines
    median_loc = df['loc'].median()
    ax3.axvline(median_loc, color='gray', linestyle='--', alpha=0.5, linewidth=1)
    ax3.axhline(0.5, color='gray', linestyle='--', alpha=0.5, linewidth=1)
    
    # Add quadrant labels
    ax3.text(median_loc * 1.5, 0.95, 'High Risk\nLarge Files', 
            fontsize=10, ha='center', va='top', style='italic', alpha=0.6)
    ax3.text(median_loc * 0.5, 0.95, 'High Risk\nSmall Files', 
            fontsize=10, ha='center', va='top', style='italic', alpha=0.6)
    
    # Overall title
    fig.suptitle(f'Bug Prediction Dashboard - {repo_name}', 
                fontsize=16, weight='bold', y=0.98)
    
    # Save
    output_path = os.path.join(output_dir, f'dashboard_{repo_name}.png')
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    
    return output_path


def create_tier_summary_table(df, repo_name, output_dir="ml/plots"):
    """
    Create a simple text-based summary table as an image.
    Shows key statistics for each tier.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.axis('tight')
    ax.axis('off')
    
    # Calculate statistics per tier
    tier_order = ['CRITICAL', 'HIGH', 'MODERATE', 'LOW']
    colors_map = {
        'CRITICAL': '#FFCDD2',  # Light red
        'HIGH': '#FFE0B2',      # Light orange
        'MODERATE': '#FFF9C4',  # Light yellow
        'LOW': '#C8E6C9'        # Light green
    }
    
    table_data = []
    table_data.append(['Tier', 'Files', '% of Total', 'Avg Risk', 'Avg LOC', 'Total LOC', 'Action'])
    
    for tier in tier_order:
        tier_df = df[df['risk_tier'] == tier]
        if len(tier_df) == 0:
            continue
        
        count = len(tier_df)
        pct = count / len(df) * 100
        avg_risk = tier_df['risk'].mean()
        avg_loc = tier_df['loc'].mean()
        total_loc = tier_df['loc'].sum()
        
        if tier == 'CRITICAL':
            action = 'Review NOW'
        elif tier == 'HIGH':
            action = 'Prioritize'
        elif tier == 'MODERATE':
            action = 'Consider'
        else:
            action = 'Low priority'
        
        table_data.append([
            tier,
            f'{count}',
            f'{pct:.1f}%',
            f'{avg_risk:.3f}',
            f'{int(avg_loc)}',
            f'{int(total_loc)}',
            action
        ])
    
    # Create table
    table = ax.table(cellText=table_data, cellLoc='center', loc='center',
                    colWidths=[0.15, 0.1, 0.12, 0.12, 0.12, 0.12, 0.15])
    
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1, 2.5)
    
    # Style header row
    for i in range(7):
        cell = table[(0, i)]
        cell.set_facecolor('#1976D2')
        cell.set_text_props(weight='bold', color='white')
    
    # Style data rows with tier colors
    for i, tier in enumerate(tier_order, start=1):
        if i < len(table_data):
            for j in range(7):
                cell = table[(i, j)]
                cell.set_facecolor(colors_map[tier])
                if j == 0:  # Tier name column
                    cell.set_text_props(weight='bold')
    
    plt.title(f'Risk Tier Summary - {repo_name}\n({len(df)} files analyzed)', 
             fontsize=14, weight='bold', pad=20)
    
    # Save
    output_path = os.path.join(output_dir, f'summary_table_{repo_name}.png')
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    
    return output_path
