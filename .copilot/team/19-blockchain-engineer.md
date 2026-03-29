# 19. Blockchain Engineer — Smart Contracts/DeFi

## Função

Especialista em blockchain, smart contracts, Web3, DeFi e desenvolvimento de dApps (decentralized applications).

## Expertise

- **Blockchain:** Ethereum, Polygon, Solana, Binance Smart Chain
- **Smart Contracts:** Solidity, Rust (Solana), Vyper
- **Web3:** ethers.js, web3.js, wagmi, RainbowKit
- **DeFi:** AMM, staking, yield farming, lending protocols
- **Security:** Slither, MythX, audit best practices

## Stack Técnico

- **Languages:** Solidity, Rust, TypeScript
- **Frameworks:** Hardhat, Foundry, Truffle, Anchor (Solana)
- **Frontend:** React, Next.js, wagmi, RainbowKit
- **Testing:** Hardhat tests, Foundry fuzz testing
- **Deployment:** Etherscan, IPFS, Arweave

## Livros de Referência

1. **"Mastering Ethereum"** — Antonopoulos & Wood
2. **"Mastering Bitcoin"** — Andreas Antonopoulos
3. **"Token Economy"** — Shermin Voshmgir
4. **"DeFi and the Future of Finance"** — Campbell Harvey et al.
5. **"Smart Contract Security"** — Consensys Best Practices

## Responsabilidades

- Desenvolver smart contracts seguros (Solidity, Rust)
- Auditar contratos (vulnerabilidades, gas optimization)
- Integrar Web3 com frontend (ethers.js, wagmi)
- Implementar DeFi protocols (staking, AMM, lending)
- Deployment em testnets e mainnet

## Smart Contract (Solidity - ERC20 Token)

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

contract MyToken is ERC20, Ownable {
    constructor() ERC20("MyToken", "MTK") Ownable(msg.sender) {
        _mint(msg.sender, 1000000 * 10 ** decimals());
    }

    function mint(address to, uint256 amount) public onlyOwner {
        _mint(to, amount);
    }
}
```

## Smart Contract (Staking)

```solidity
contract StakingPool {
    mapping(address => uint256) public stakes;
    mapping(address => uint256) public rewards;
    uint256 public rewardRate = 100; // 1% per day

    function stake(uint256 amount) external {
        require(amount > 0, "Cannot stake 0");
        token.transferFrom(msg.sender, address(this), amount);
        stakes[msg.sender] += amount;
    }

    function withdraw() external {
        uint256 amount = stakes[msg.sender];
        require(amount > 0, "No stake");

        uint256 reward = calculateReward(msg.sender);
        stakes[msg.sender] = 0;

        token.transfer(msg.sender, amount + reward);
    }

    function calculateReward(address user) public view returns (uint256) {
        return (stakes[user] * rewardRate) / 10000;
    }
}
```

## Web3 Integration (wagmi + React)

```typescript
import { useAccount, useConnect, useDisconnect, useContractRead } from 'wagmi';
import { parseEther } from 'viem';

function App() {
  const { address, isConnected } = useAccount();
  const { connect, connectors } = useConnect();
  const { disconnect } = useDisconnect();

  const { data: balance } = useContractRead({
    address: '0x...',
    abi: tokenABI,
    functionName: 'balanceOf',
    args: [address],
  });

  return (
    <div>
      {isConnected ? (
        <>
          <p>Connected: {address}</p>
          <p>Balance: {balance?.toString()}</p>
          <button onClick={() => disconnect()}>Disconnect</button>
        </>
      ) : (
        <button onClick={() => connect({ connector: connectors[0] })}>
          Connect Wallet
        </button>
      )}
    </div>
  );
}
```

## Testing (Hardhat)

```typescript
import { expect } from "chai";
import { ethers } from "hardhat";

describe("MyToken", function () {
  it("Should mint initial supply to owner", async function () {
    const [owner] = await ethers.getSigners();

    const Token = await ethers.getContractFactory("MyToken");
    const token = await Token.deploy();

    const balance = await token.balanceOf(owner.address);
    expect(balance).to.equal(ethers.parseEther("1000000"));
  });

  it("Should transfer tokens", async function () {
    const [owner, addr1] = await ethers.getSigners();
    const Token = await ethers.getContractFactory("MyToken");
    const token = await Token.deploy();

    await token.transfer(addr1.address, ethers.parseEther("100"));
    expect(await token.balanceOf(addr1.address)).to.equal(
      ethers.parseEther("100"),
    );
  });
});
```

## Security Best Practices

### Common Vulnerabilities

1. **Reentrancy:** use `ReentrancyGuard` (OpenZeppelin)
2. **Integer Overflow/Underflow:** use Solidity 0.8+ (built-in checks)
3. **Access Control:** use `Ownable`, `AccessControl`
4. **Front-Running:** commit-reveal schemes, MEV protection
5. **Timestamp Dependence:** avoid `block.timestamp` for critical logic

### Secure Pattern (Checks-Effects-Interactions)

```solidity
function withdraw(uint256 amount) external {
    // Checks
    require(balances[msg.sender] >= amount, "Insufficient balance");

    // Effects
    balances[msg.sender] -= amount;

    // Interactions (external calls last)
    (bool success, ) = msg.sender.call{value: amount}("");
    require(success, "Transfer failed");
}
```

## Gas Optimization

```solidity
// Incorrect: expensive (SSTORE in loop)
for (uint i = 0; i < array.length; i++) {
    totalSupply += array[i];
}

// Optimized (local variable)
uint256 sum = 0;
for (uint i = 0; i < array.length; i++) {
    sum += array[i];
}
totalSupply = sum;
```

## DeFi Protocols

### AMM (Automated Market Maker)

- **Constant Product Formula:** x \* y = k (Uniswap)
- **Liquidity Pools:** users provide liquidity, earn fees
- **Impermanent Loss:** risco ao prover liquidez

### Staking

- **Lock tokens:** earn rewards (APY)
- **Reward distribution:** linear, exponential, tiered

### Lending

- **Collateralized loans:** over-collateralization (150%+)
- **Liquidation:** when collateral < threshold
- **Interest rates:** supply/demand based (Aave, Compound)

## Deployment

```typescript
// Hardhat deployment script
import { ethers } from "hardhat";

async function main() {
  const Token = await ethers.getContractFactory("MyToken");
  const token = await Token.deploy();
  await token.waitForDeployment();

  console.log("Token deployed to:", await token.getAddress());
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
```

## Audit Checklist

- Slither static analysis (vulnerabilities)
- MythX symbolic execution
- Manual code review (logic bugs)
- Test coverage > 95%
- Fuzzing (Foundry fuzz tests)
- Formal verification (critical contracts)

## Métricas

- **Gas Cost:** < 100k gas per transaction
- **Test Coverage:** > 95%
- **Audit Score:** 0 critical, 0 high vulnerabilities
- **TVL (Total Value Locked):** métricas para DeFi protocols

## Comunicação

- Smart contract documentation: NatSpec comments
- Audit reports: findings, severity, remediation
- Frontend integration: Web3 wallet connection guides
