using System;
using System.Threading;
using Lumina.Execution.V1;

namespace Lumina.Execution.Fabric.Safety
{
    /// <summary>
    /// Fabric-side safe mode: NORMAL → SAFE → FULL_SAFE (blueprint §6.3).
    /// Independent of Brain process.
    /// </summary>
    public sealed class SafeModeStateMachine
    {
        private int _state = (int)SafeModeState.Normal;
        private readonly object _gate = new object();

        public SafeModeState State
        {
            get => (SafeModeState)Volatile.Read(ref _state);
            private set => Volatile.Write(ref _state, (int)value);
        }

        public bool AcceptsNewOrders => State == SafeModeState.Normal;

        public event Action<SafeModeState, string>? StateChanged;

        public void EnterSafe(string reason)
        {
            Transition(SafeModeState.Safe, reason);
        }

        public void EnterFullSafe(string reason)
        {
            Transition(SafeModeState.FullSafe, reason);
        }

        public void ClearToNormal(string reason)
        {
            Transition(SafeModeState.Normal, reason);
        }

        private void Transition(SafeModeState next, string reason)
        {
            lock (_gate)
            {
                if (State == next)
                    return;
                // FULL_SAFE can only clear via explicit ClearToNormal.
                if (State == SafeModeState.FullSafe && next == SafeModeState.Safe)
                    return;
                State = next;
            }
            StateChanged?.Invoke(next, reason ?? string.Empty);
        }
    }
}
