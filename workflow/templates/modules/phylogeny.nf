/*
 * 系统发育分析模块
 * 使用 IQ-Tree2 构建进化树
 */
process PHYLOGENY {
    tag "${sequences}"

    publishDir "${params.outdir}/phylogeny", mode: 'copy'

    input:
        path(sequences)

    output:
        path("tree.nwk"), emit: tree
        path("tree_stats.txt"), emit: stats

    script:
    """
    # 合并所有序列
    cat ${sequences} > all_sequences.fa

    # 运行 IQ-Tree2
    iqtree2 \\
        -s all_sequences.fa \\
        -m MFP \\
        -bb 1000 \\
        -nt AUTO \\
        -o outgroup

    # 提取进化树
    mv all_sequences.fa.treefile tree.nwk

    # 保存统计信息
    echo "进化分析完成" > tree_stats.txt
    """
}
