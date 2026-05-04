from pdf2md.conventions.alignment import align_groundtruth_to_backend


def test_missed_object_is_reported_explicitly():
    gt={"objects":[{"gt_id":"d:eq:1","doc_id":"d","object_type":"equation","body_key":"emc2","required":True}]}
    rec=align_groundtruth_to_backend(gt,[],backend="backend_a",doc_id="d")[0]
    assert rec["status"]=="missed"
    assert rec["unmatched_reason"]
    assert rec["matched_blocks"]==[]
