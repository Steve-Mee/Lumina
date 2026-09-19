namespace Lumina.Execution.Fabric.Safety
{
    /// <summary>
    /// Fail-closed gates for watchdog emergency flatten. All must pass or no order is submitted.
    /// </summary>
    public static class EmergencyFlattenPolicy
    {
        public static string? DenyReason(bool armed, int positionCount, int workingCount, int sessionTouchedCount)
        {
            if (!armed)
                return "unarmed";
            if (sessionTouchedCount <= 0)
                return "no_session_orders";
            if (positionCount <= 0 && workingCount <= 0)
                return "empty_book";
            return null;
        }
    }
}
