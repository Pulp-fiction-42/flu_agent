/*
 * 流感病毒进化分析流程
 * Nextflow DSL2 模板
 *
 * 构建系统发育树
 */
nextflow.enable.dsl = 2

params.sequences = "$params.outdir/sequences/*.fasta"
params.outdir = "$params.outdir"
params.tree_method = "iqtree"  // iqtree, raxml, fasttree
params.thread = 4

println "========================================="
println "流感病毒进化分析流程"
println "========================================="

workflow {
    main:
        seq_ch = channel.fromPath(params.sequences)

        // 多序列比对 (MAFFT)
        // 修剪 (trimAl)
        // 建树 (IQ-Tree)
        // 进化树可视化
}

workflow.onComplete {
    println "进化分析完成!"
}