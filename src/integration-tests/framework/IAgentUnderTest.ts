export interface IAgentUnderTest {
  readonly agentId: string;
  readonly baseUrl: string;
  readonly apiKey: string;
  readonly displayName: string;
  /** Environment variable that gates the test suite (e.g. LETTA_RUN_SCISSARI_TEST). */
  readonly enableFlag: string;
  /** Tools the agent must have. Tool-parity tests fail if any are missing. */
  readonly requiredTools?: readonly string[];
  /** Tools that must NOT be present (legacy defaults that indicate a reset). */
  readonly legacyTools?: readonly string[];
}
