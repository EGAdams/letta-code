from intake.statuses import ScannerIntakeStatusResponse


def test_scanner_status_exposes_the_isolated_conversation():
    response = ScannerIntakeStatusResponse.from_intake({
        'status': 'PASS', 'conversation_id': 'conv-scan-123',
        'dispatched_at': 1_725_900_000.25})

    assert response.model_dump(exclude_none=True) == {
        'ok': True, 'status': 'pass', 'conversation_id': 'conv-scan-123',
        'dispatched_at': 1_725_900_000.25}


def test_scanner_status_drops_a_malformed_conversation_id():
    response = ScannerIntakeStatusResponse.from_intake({
        'status': 'pass', 'conversation_id': 'conv-ok;echo wrong'})

    assert response.model_dump(exclude_none=True) == {
        'ok': True, 'status': 'pass'}


def test_missing_intake_is_idle_without_a_conversation():
    response = ScannerIntakeStatusResponse.from_intake(None)

    assert response.model_dump(exclude_none=True) == {
        'ok': True, 'status': 'idle'}


def test_scanner_status_drops_a_malformed_dispatch_timestamp():
    response = ScannerIntakeStatusResponse.from_intake({
        'status': 'processing', 'dispatched_at': 'yesterday'})

    assert response.model_dump(exclude_none=True) == {
        'ok': True, 'status': 'processing'}
