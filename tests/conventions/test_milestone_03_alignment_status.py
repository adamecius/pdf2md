from pdf2md.conventions.alignment import align_groundtruth_to_backend


def test_alignment_unsupported_status():
    gt={"objects":[{"gt_id":"x","doc_id":"d","object_type":"unsupported_type","required":True}]}
    rec=align_groundtruth_to_backend(gt,[],backend="backend_a",doc_id="d")[0]
    assert rec["status"] in {"unsupported","missed"}
