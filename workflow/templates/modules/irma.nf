/*
 * IRMA 流感病毒组装模块
 * 基于 IRMA (Iterative Refinement Meta-Assembler)
 */
process IRMA_ASSEMBLY {
    tag "${reads}"

    publishDir "${params.outdir}/assembly", mode: 'copy'

    input:
        path(reads)
        val(segment)

    output:
        path("irma_results/*.fa"), emit: assembly
        path("irma_results/*.csv"), emit: summary
        path("irma_results/"), emit: results_dir

    script:
    """
    # 创建输入目录链接
    mkdir -p input
    ln -sf ${reads} input/reads.fastq.gz

    # 运行 IRMA
    irma \\
        --no-force \\
        --clean \\
        ${segment} \\
        input/reads.fastq.gz \\
        irma_results

    # 重命名输出文件
    cd irma_results
    for f in *. consensus.*; do
        [ -f "\$f" ] && mv "\$f" "\${f##*.}.fa"
    done
    """
}
